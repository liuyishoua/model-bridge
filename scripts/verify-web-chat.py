"""Exercise the actual WebUI saved-chat + WebSocket protocol, not only its API alias."""
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REMOTE = r'''
import asyncio, json, time, uuid
import aiohttp, socketio

BASE = 'https://d.58nft.net'
MODEL = 'leo-gpt-oss:20b'

async def main():
    sio = socketio.AsyncClient()
    finished = asyncio.Event()
    completed = asyncio.Event()
    types = []
    errors = []
    assistant_id = str(uuid.uuid4())
    chat_id = None
    token = None
    @sio.on('events')
    async def events(event):
        if event.get('message_id') != assistant_id:
            return
        data = event.get('data') or {}
        kind = data.get('type')
        types.append(kind)
        body = data.get('data') or {}
        if kind == 'chat:message:error':
            errors.append(body.get('error')); finished.set()
        if kind == 'chat:completion' and body.get('done'):
            completed.set()
        if kind == 'chat:active' and body.get('active') is False:
            finished.set()
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=180)) as http:
        async def call(method, path, payload=None):
            headers = {'Authorization': 'Bearer ' + token} if token else {}
            async with http.request(method, BASE + path, json=payload, headers=headers) as r:
                value = await r.json()
                assert r.status < 400, (path, r.status, value)
                return value
        auth = await call('POST', '/api/v1/auths/signin', CREDENTIALS)
        token = auth['token']
        assert auth['role'] == 'admin'
        try:
            await sio.connect(BASE, socketio_path='ws/socket.io', transports=['websocket'])
            joined = await sio.call('user-join', {'auth': {'token': token}}, timeout=20)
            assert joined['id'] == auth['id']
            await call('GET', '/api/models')
            user_id = str(uuid.uuid4())
            prompt = 'What is 17 times 19? Reply briefly.'
            payload = {
                'model': MODEL, 'stream': True, 'parent_id': None,
                'id': assistant_id, 'session_id': sio.get_sid(),
                'messages': [{'role': 'user', 'content': prompt}],
                'user_message': {'id': user_id, 'role': 'user', 'content': prompt,
                    'parentId': None, 'childrenIds': [], 'models': [MODEL],
                    'timestamp': int(time.time())},
                'params': {'temperature': 0, 'num_predict': 256},
                'background_tasks': {'title_generation': True,
                    'tags_generation': True, 'follow_up_generation': True},
            }
            started = time.monotonic()
            response = await call('POST', '/api/chat/completions', payload)
            chat_id = response['chat_id']
            assert response['status'] is True
            await asyncio.wait_for(finished.wait(), timeout=120)
            assert not errors, errors
            assert completed.is_set(), types
            stored = await call('GET', '/api/v1/chats/' + chat_id)
            message = stored['chat']['history']['messages'][assistant_id]
            answer = message.get('content', '')
            assert '323' in answer, message
            assert message.get('done') is True
            print(json.dumps({'websocket_connected': True,
                'admin_saved_chat': True, 'stream_completed': True,
                'background_tasks_enabled': True, 'answer': answer,
                'title': stored['chat'].get('title'),
                'event_types': sorted(set(types)),
                'seconds': round(time.monotonic() - started, 2)}, ensure_ascii=True))
        finally:
            if chat_id:
                await call('DELETE', '/api/v1/chats/' + chat_id)
            if sio.connected:
                await sio.disconnect()
asyncio.run(main())
'''

def main():
    credentials = json.loads((ROOT / 'data/credentials.json').read_text())
    auth = {'email': credentials['admin_email'], 'password': credentials['admin_password']}
    code = 'CREDENTIALS = ' + repr(auth) + '\n' + REMOTE
    result = subprocess.run([
        'ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=15',
        'ubuntu@100.73.83.110', 'sudo docker exec -i leo-model-webui python -',
    ], input=code.encode(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode:
        print(result.stderr.decode(errors='replace'))
        raise SystemExit(result.returncode)
    data = json.loads(result.stdout)
    (ROOT / 'artifacts').mkdir(exist_ok=True)
    (ROOT / 'artifacts/web-chat-test.json').write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(data, ensure_ascii=True, indent=2))

if __name__ == '__main__': main()
