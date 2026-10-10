"""Public website acceptance in real Chromium; all chat actions happen through UI."""
import asyncio
import json
import os
import re
import time
from pathlib import Path
from playwright.async_api import async_playwright, expect

BASE = os.environ.get('MODEL_TEST_BASE', 'https://d.58nft.net').rstrip('/')
OUT = Path('/artifacts')
ASSISTANTS = '#messages-container [id^="message-"]:not(.user-message)'

async def case(browser, credentials, name, username, password, mobile, turns):
    context = await browser.new_context(
        viewport={'width': 430, 'height': 900} if mobile else {'width': 1280, 'height': 900},
        is_mobile=mobile, has_touch=mobile, locale='zh-CN', timezone_id='Asia/Shanghai',
    )
    page = await context.new_page()
    errors = []
    chat_requests = []
    websocket_frames = {'received': 0}
    def response_received(response):
        if response.url.split('?')[0].endswith('/api/chat/completions'):
            payload = response.request.post_data_json or {}
            chat_requests.append({'status': response.status, 'model': payload.get('model'), 'stream': payload.get('stream'),
                'messages': [{k: m.get(k) for k in ('role', 'content')} for m in payload.get('messages', [])],
                'params': payload.get('params')})
    def websocket_opened(socket):
        def received(_): websocket_frames['received'] += 1
        socket.on('framereceived', received)
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.on('response', response_received)
    page.on('websocket', websocket_opened)
    result = {'name': name, 'mobile': mobile, 'turns': [], 'ok': False}
    try:
        await page.goto(BASE, wait_until='domcontentloaded', timeout=60000)
        await page.locator('#username').fill(username)
        await page.locator('#password').fill(password)
        await page.get_by_role('button', name='登录', exact=True).click()
        await page.locator('#chat-input').wait_for(state='visible', timeout=60000)
        result['login_through_page'] = True
        print('BROWSER_LOGIN_OK ' + name, flush=True)
        for index, (question, pattern) in enumerate(turns):
            old_count = await page.locator(ASSISTANTS).count()
            await page.locator('#chat-input').fill(question)
            start = time.monotonic()
            await page.locator('#send-message-button').click()
            print('BROWSER_SENT ' + name + ' turn=' + str(index + 1), flush=True)
            await expect(page.locator(ASSISTANTS)).to_have_count(old_count + 1, timeout=120000)
            answer = page.locator(ASSISTANTS).last.locator('.markdown-prose:visible')
            await answer.wait_for(state='visible', timeout=120000)
            await expect(answer).not_to_have_text('', timeout=120000)
            first_visible = round(time.monotonic() - start, 2)
            await page.locator('button[aria-label="Stop"],button[aria-label="停止"]').wait_for(state='hidden', timeout=120000)
            rendered = await answer.inner_text()
            assert re.search(pattern, rendered), 'Unexpected rendered answer: ' + rendered
            assert not re.search('GPU.*busy|queue.*full|Model not found', rendered, re.I), rendered
            if '从17×1到17×9' in question:
                rows = await answer.locator('tbody tr').all_inner_texts()
                assert len(rows) == 9, 'Expected nine rendered table rows: ' + repr(rows)
                for multiplier, row in enumerate(rows, start=1):
                    assert re.findall(r'\d+', row) == ['17', str(multiplier), str(17 * multiplier)], row
            screenshot = name + '-turn-' + str(index + 1) + '.png'
            await page.screenshot(path=str(OUT/screenshot), full_page=True)
            result['turns'].append({'question': question, 'rendered_answer': rendered,
                'visible_answer_seconds': first_visible, 'completed_seconds': round(time.monotonic() - start, 2),
                'screenshot': screenshot})
            print('VISIBLE_ANSWER_OK ' + name + ' ' + json.dumps(rendered, ensure_ascii=True), flush=True)
        result['chat_url'] = page.url
        await page.reload(wait_until='domcontentloaded')
        await page.locator('#chat-input').wait_for(state='visible', timeout=60000)
        await expect(page.locator(ASSISTANTS)).to_have_count(len(turns), timeout=60000)
        reloaded_answer = page.locator(ASSISTANTS).last.locator('.markdown-prose:visible')
        await reloaded_answer.wait_for(state='visible', timeout=60000)
        await expect(reloaded_answer).not_to_have_text('', timeout=60000)
        # inner_text preserves table cell boundaries; textContent concatenates cells.
        assert re.search(turns[-1][1], await reloaded_answer.inner_text()), 'Reloaded answer changed'
        result['answers_survive_reload'] = True
        await page.screenshot(path=str(OUT/(name + '-reloaded.png')), full_page=True)
        assert not errors, errors
        assert len(chat_requests) >= len(turns), chat_requests
        assert all(r['status'] == 200 and r['model'] == 'leo-gpt-oss:20b' for r in chat_requests), chat_requests
        assert websocket_frames['received'] > 0, 'Browser did not receive WebSocket events'
        result['ok'] = True
    except Exception as error:
        result['error'] = str(error)
        result['page_text'] = await page.locator('body').inner_text()
        await page.screenshot(path=str(OUT/(name + '-failure.png')), full_page=True)
        print('BROWSER_CASE_FAILED ' + name + ' ' + str(error), flush=True)
    finally:
        result.update(page_errors=errors, chat_requests=chat_requests, websocket_frames=websocket_frames)
        await context.close()
    return result

async def main():
    credentials = json.loads(Path('/run/browser-credentials.json').read_text())
    OUT.mkdir(exist_ok=True)
    result = {'public_url': BASE, 'checked_at': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
        'browser': 'Chromium / Playwright 1.63.0 / Linux Docker', 'cases': []}
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            cases = [
                ('admin-mobile', 'leo', credentials['admin_password'], True, [
                    ('请用中文回答：17乘以19是多少？只给出结果。', r'^323$'),
                    ('把刚才的计算结果再加7，是多少？只给出结果。', r'^330$'),
                    ('请给我17的乘法表，从17×1到17×9，使用Markdown表格。', r'\b153\b'),
                ]),
                ('user-mobile', credentials['client_email'], credentials['client_password'], True, [
                    ('有3盒铅笔，每盒12支，送出5支，还剩多少支？用中文简短回答并给出算式。', r'31'),
                    ('如果再买两支，现在有多少支？请用一句中文回答。', r'33'),
                ]),
                ('user-desktop', credentials['client_email'], credentials['client_password'], False, [
                    ('请用两句中文解释，为什么白天能看到蓝色的天空？', r'散射|蓝光'),
                ]),
            ]
            for name, username, password, mobile, turns in cases:
                result['cases'].append(await case(browser, credentials, name, username, password, mobile, turns))
                (OUT/'e2e-result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf8')
                if not result['cases'][-1]['ok']:
                    break
        finally:
            await browser.close()
    result['ok'] = len(result['cases']) == 3 and all(c['ok'] for c in result['cases'])
    (OUT/'e2e-result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf8')
    print(json.dumps(result, ensure_ascii=True, indent=2), flush=True)
    if not result['ok']:
        raise SystemExit(1)

asyncio.run(main())
