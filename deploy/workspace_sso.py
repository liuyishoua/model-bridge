"""Bind Open WebUI HTTP and Socket.IO identities to the central workspace.

Trusted headers are supplied only by the loopback Caddy upstream. Central
verification remains authoritative for live sockets; no passwords are copied.
"""
import asyncio
from contextlib import suppress
from http.cookies import SimpleCookie
import json
import os
from urllib.error import HTTPError
from urllib.request import Request as URLRequest, build_opener, ProxyHandler

from fastapi.responses import JSONResponse

IDENTITY_URL = os.getenv('WORKSPACE_IDENTITY_URL', 'https://d.58nft.net:9461/api/auth/workspace/verify')
SOCKET_RECHECK_SECONDS = 15
API_PATHS = frozenset(('/api/models', '/api/chat/completions'))


def workspace_token(headers):
    cookies = SimpleCookie()
    try:
        cookies.load(headers.get('cookie', ''))
        return cookies['ops_workspace_session'].value if 'ops_workspace_session' in cookies else ''
    except Exception:
        return ''


def verify_workspace(token):
    if not token:
        return None
    try:
        req = URLRequest(IDENTITY_URL, headers={'Authorization': 'Bearer ' + token})
        with build_opener(ProxyHandler({})).open(req, timeout=4) as response:
            identity = json.load(response)
        if type(identity.get('id')) is int and identity.get('app_access', {}).get('model-bridge') is True:
            return identity
    except (HTTPError, OSError, ValueError):
        pass
    return None


def logout_workspace(token):
    req = URLRequest(IDENTITY_URL.removesuffix('/verify') + '/logout', data=b'{}',
                     headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
    with build_opener(ProxyHandler({})).open(req, timeout=4) as response:
        return [value for value in response.headers.get_all('Set-Cookie', [])
                if value.startswith('ops_workspace_session=')]


def install(app):
    from open_webui.models.users import Users
    from open_webui.utils.auth import get_verified_user_by_token
    from open_webui.socket import main as sockets

    @app.middleware('http')
    async def enforce_identity(request, call_next):
        path = request.url.path
        api_key = request.headers.get('authorization', '').startswith('Bearer sk-') and path in API_PATHS
        email = request.headers.get('x-workspace-email', '')
        if path.startswith(('/api/', '/ollama/', '/openai/', '/pipelines/')) and not api_key:
            if not email or not workspace_token(request.headers):
                return JSONResponse({'detail': '请先登录彩虹桥。'}, 401)
            if path in ('/api/v1/auths/signup', '/api/v1/auths/add', '/api/v1/auths/update/password', '/api/v1/auths/ldap'):
                return JSONResponse({'detail': '账号和密码请在彩虹桥管理。'}, 403)
            if path.startswith('/api/v1/users/') and request.method in ('POST', 'DELETE'):
                tail = path.removeprefix('/api/v1/users/').strip('/')
                if request.method == 'DELETE' and '/' not in tail or tail.endswith('/update') and tail.count('/') == 1 and tail.split('/')[0] not in ('user', 'default'):
                    return JSONResponse({'detail': '用户和角色请在彩虹桥管理。'}, 403)
            user = await Users.get_user_by_email(email)
            role = request.headers.get('x-workspace-role')
            if role not in ('admin', 'user'):
                return JSONResponse({'detail': '统一身份不完整。'}, 401)
            if user and user.role != role:
                await Users.update_user_role_by_id(user.id, role)
            if path == '/api/v1/auths/signout' and request.method == 'POST':
                expected_origin = os.getenv('WEBUI_URL', '').rstrip('/') or str(request.base_url).rstrip('/')
                if request.headers.get('origin') != expected_origin:
                    return JSONResponse({'detail': '请在模型聊天中退出。'}, 403)
                raw = request.headers.get('authorization', '')
                token = raw.removeprefix('Bearer ') if raw.startswith('Bearer ') else request.cookies.get('token', '')
                try:
                    subject = await get_verified_user_by_token(token)
                except Exception:
                    subject = None
                # An old tab must rebind to the new user, never log that user out.
                matches = subject and subject.email == email
                response = JSONResponse({'status': True, 'redirect_url': 'https://d.58nft.net/' if matches else '/'})
                if matches:
                    try:
                        cookies = await asyncio.to_thread(logout_workspace, workspace_token(request.headers))
                    except (OSError, HTTPError):
                        return JSONResponse({'detail': '暂时无法退出，请重试。'}, 503)
                    for cookie in cookies:
                        response.headers.append('Set-Cookie', cookie)
                response.delete_cookie('token', path='/')
                return response
        return await call_next(request)

    # Native Socket.IO accepts a separate token in the connect/user-join packet.
    # Check its subject as well as the HTTP upgrade to prevent stale-account joins.
    originals = dict(sockets.sio.handlers['/'])
    watchers = {}

    async def bound_user(environ, token):
        scope = (environ or {}).get('asgi.scope') or {}
        headers = {k.decode('latin1').lower(): v.decode('latin1') for k, v in scope.get('headers', [])}
        central = await asyncio.to_thread(verify_workspace, workspace_token(headers))
        if not central or str(central['id']) != headers.get('x-workspace-id'):
            return None
        try:
            user = await get_verified_user_by_token(token)
        except Exception:
            return None
        if not user or user.email != headers.get('x-workspace-email'):
            return None
        role = 'admin' if central.get('role') == 'admin' else 'user'
        if user.role != role:
            user = await Users.update_user_role_by_id(user.id, role)
        return user

    async def watch(sid, environ, token):
        try:
            while True:
                await asyncio.sleep(SOCKET_RECHECK_SECONDS)
                user = await bound_user(environ, token)
                if not user:
                    await sockets.sio.disconnect(sid)
                    return
                session = await sockets.sio.get_session(sid)
                if session.get('user'):
                    session['user']['role'] = user.role
                    await sockets.sio.save_session(sid, session)
                    sockets.SESSION_POOL[sid] = session['user']
        except asyncio.CancelledError:
            raise
        except Exception:
            with suppress(Exception):
                await sockets.sio.disconnect(sid)
        finally:
            watchers.pop(sid, None)

    async def connect(sid, environ, auth):
        token = auth.get('token', '') if isinstance(auth, dict) else ''
        if not await bound_user(environ, token):
            return False
        result = await originals['connect'](sid, environ, auth)
        watchers[sid] = asyncio.create_task(watch(sid, environ, token))
        return result

    async def user_join(sid, data):
        auth = data.get('auth') if isinstance(data, dict) else None
        token = auth.get('token', '') if isinstance(auth, dict) else ''
        if not await bound_user(sockets.sio.get_environ(sid), token):
            await sockets.sio.disconnect(sid)
            return
        return await originals['user-join'](sid, data)

    async def disconnect(sid, *args):
        watcher = watchers.pop(sid, None)
        if watcher and watcher is not asyncio.current_task():
            watcher.cancel()
            with suppress(asyncio.CancelledError):
                await watcher
        if originals.get('disconnect'):
            return await originals['disconnect'](sid, *args)

    sockets.sio.on('connect', handler=connect)
    sockets.sio.on('user-join', handler=user_join)
    sockets.sio.on('disconnect', handler=disconnect)
