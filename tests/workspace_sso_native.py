"""Run inside the pinned Open WebUI image; all users/data are temporary."""
import asyncio
from contextlib import asynccontextmanager
import importlib.util
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

runtime = tempfile.TemporaryDirectory(prefix='workspace-sso-native-')
os.environ.update(WEBUI_URL='https://model.test', DATA_DIR=runtime.name, DATABASE_URL='sqlite:///' + runtime.name + '/test.db',
                  WEBUI_SECRET_KEY='synthetic-test-key-not-production',
                  ENABLE_DB_MIGRATIONS='false', ENABLE_OLLAMA_API='false', ENABLE_OPENAI_API='false',
                  WEBUI_AUTH_TRUSTED_EMAIL_HEADER='X-Workspace-Email',
                  WEBUI_AUTH_TRUSTED_NAME_HEADER='X-Workspace-Name',
                  WEBUI_AUTH_TRUSTED_ROLE_HEADER='X-Workspace-Role', ENABLE_SIGNUP='false',
                  ENABLE_LOGIN_FORM='false', ENABLE_API_KEYS='true')

from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient
from open_webui.routers import auths, chats
from open_webui.config import seed_registered_defaults
from open_webui.internal.db import Base, engine
from open_webui.models.users import Users
from open_webui.models.auths import Auths
from open_webui.models.chats import Chats
from open_webui.utils.auth import get_current_user
from open_webui.socket import main as sockets

spec=importlib.util.spec_from_file_location('workspace_sso_qa', '/tmp/workspace-sso-qa/workspace_sso.py')
sso=importlib.util.module_from_spec(spec);spec.loader.exec_module(sso)
import importlib, pkgutil
import open_webui.models
for module in pkgutil.iter_modules(open_webui.models.__path__):
    importlib.import_module('open_webui.models.'+module.name)
Base.metadata.create_all(engine)

@asynccontextmanager
async def lifespan(app):
    await seed_registered_defaults()
    yield

app=FastAPI(lifespan=lifespan)
app.state.redis=None
app.include_router(auths.router, prefix='/api/v1/auths')
app.include_router(chats.router, prefix='/api/v1/chats')

@app.get('/api/private')
async def private(user=Depends(get_current_user)):
    return {'id':user.id,'role':user.role,'email':user.email}

sso.install(app)

def identity(uid,role='user'):
    return {'X-Workspace-Id':str(uid),'X-Workspace-Email':f'workspace-{uid}@bifrost.local',
            'X-Workspace-Name':f'synthetic-{uid}','X-Workspace-Role':role,
            'Cookie':'ops_workspace_session=synthetic-workspace-'+str(uid)}

with TestClient(app, base_url='https://model.test') as client:
    def signin(uid,role='user'):
        response=client.post('/api/v1/auths/signin',headers=identity(uid,role),json={'email':'ignored@attacker.test','password':'ignored'})
        assert response.status_code==200,(response.status_code,response.text)
        return response.json()
    a=signin(101,'admin');b=signin(102)
    assert a['id']!=b['id'] and a['role']=='admin' and b['role']=='user'
    assert a['email']=='workspace-101@bifrost.local'
    again=signin(101,'admin');assert again['id']==a['id']
    ha={**identity(101,'admin'),'Authorization':'Bearer '+a['token']}
    hb={**identity(102),'Authorization':'Bearer '+b['token']}
    assert client.get('/api/private',headers=ha).json()['id']==a['id']
    assert client.get('/api/private',headers={**hb,'Authorization':'Bearer '+a['token']}).status_code==401
    assert client.post('/api/v1/auths/signup',headers=hb,json={'email':'new@test','password':'x','name':'x'}).status_code==403
    assert client.post('/api/v1/auths/update/password',headers=hb,json={'password':'x','new_password':'y'}).status_code==403
    assert client.get('/api/private',headers={**identity(101),'Authorization':'Bearer '+a['token']}).json()['role']=='user'
    assert client.get('/api/private',headers={'Authorization':'Bearer '+a['token']}).status_code==401
    own=client.post('/api/v1/chats/new',headers={**identity(101),'Authorization':'Bearer '+a['token']},json={'chat':{'title':'Synthetic private A','history':{'messages':{},'currentId':None}}})
    assert own.status_code==200,own.text
    chat_id=own.json()['id']
    assert client.get('/api/v1/chats/'+chat_id,headers=hb).status_code==401
    assert client.get('/api/v1/chats/'+chat_id,headers={**identity(101),'Authorization':'Bearer '+a['token']}).status_code==200
    assert signin(101)['id']==a['id']
    with patch.object(sso,'logout_workspace',return_value=['ops_workspace_session=; Path=/; Max-Age=0']) as revoke:
        stale=client.post('/api/v1/auths/signout',headers={**hb,'Authorization':'Bearer '+a['token'],'Origin':'https://model.test'})
        assert stale.status_code==200 and stale.json()['redirect_url']=='/'
        revoke.assert_not_called()
        assert client.post('/api/v1/auths/signout',headers={**hb,'Origin':'https://evil.test'}).status_code==403
        current=client.post('/api/v1/auths/signout',headers={**hb,'Origin':'https://model.test'})
        assert current.status_code==200
        revoke.assert_called_once_with('synthetic-workspace-102')
    async def socket_checks():
        def environ(uid):return {'asgi.scope':{'headers':[(k.lower().encode(),v.encode()) for k,v in identity(uid).items()]}}
        native_connect=AsyncMock();native_disconnect=AsyncMock()
        # Registered wrappers captured native callbacks at install; use real connect
        # rejection before the original handler is invoked (no network socket required).
        with patch.object(sso,'verify_workspace',return_value={'id':102,'role':'user','app_access':{'model-bridge':True}}):
            assert await sockets.sio.handlers['/']['connect']('wrong-subject',environ(102),{'token':a['token']}) is False
        with patch.object(sso,'verify_workspace',return_value=None):
            assert await sockets.sio.handlers['/']['connect']('revoked',environ(102),{'token':b['token']}) is False
        with patch.object(sso,'verify_workspace',return_value={'id':102,'role':'user','app_access':{'model-bridge':True}}),patch.object(sockets.sio,'disconnect',native_disconnect),patch.object(sockets.sio,'get_environ',return_value=environ(102)):
            await sockets.sio.handlers['/']['user-join']('wrong-rejoin',{'auth':{'token':a['token']}})
            native_disconnect.assert_awaited_once_with('wrong-rejoin')
        sso.SOCKET_RECHECK_SECONDS=0.01
        native_disconnect.reset_mock()
        with patch.object(sso,'verify_workspace',side_effect=[{'id':102,'role':'user','app_access':{'model-bridge':True}},None]),patch.object(sockets.sio,'save_session',AsyncMock()),patch.object(sockets.sio,'enter_room',AsyncMock()),patch.object(sockets.sio,'disconnect',native_disconnect):
            await sockets.sio.handlers['/']['connect']('live-revoked',environ(102),{'token':b['token']})
            await asyncio.sleep(0.1)
            native_disconnect.assert_awaited_once_with('live-revoked')
    asyncio.run(socket_checks())
print(json.dumps({'native_sso':'passed','users':'temporary','cases':['stable_personal_identity','two_accounts_isolated','stale_token_rejected','role_revocation','local_password_disabled','socket_wrong_subject','socket_revoked','socket_rejoin_wrong_subject','private_chats_isolated','live_socket_revoked','stale_logout_does_not_revoke_new_user','logout_revokes_current_identity']}))
runtime.cleanup()
