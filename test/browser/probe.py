"""Real Chromium diagnostic: submit login in the public web page and inspect UI."""
import asyncio
import json
from pathlib import Path
from playwright.async_api import async_playwright

BASE = 'https://43.172.70.56'
OUT = Path('/artifacts')

async def main():
    creds = json.loads(Path('/run/browser-credentials.json').read_text())
    OUT.mkdir(exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={'width': 430, 'height': 900}, is_mobile=True, has_touch=True)
        page = await context.new_page()
        page_errors = []
        failed = []
        page.on('pageerror', lambda error: page_errors.append(str(error)))
        page.on('requestfailed', lambda req: failed.append({'url': req.url.split('?')[0], 'failure': req.failure}))
        try:
            await page.goto(BASE, wait_until='domcontentloaded', timeout=60000)
            await page.locator('#username').fill('leo')
            await page.locator('#password').fill(creds['admin_password'])
            await page.get_by_role('button', name='登录', exact=True).click()
            await page.locator('#chat-input').wait_for(state='visible', timeout=60000)
            await page.locator('#chat-input').fill('请用中文回答：17乘以19是多少？只给出结果。')
            await page.locator('#send-message-button').click()
            print('REAL_BROWSER_MESSAGE_SUBMITTED', flush=True)
            await page.wait_for_function("document.body.innerText.includes('323')", timeout=180000)
            await page.wait_for_timeout(2000)
            await page.screenshot(path=str(OUT/'admin-after-login.png'), full_page=True)
            dom = await page.locator('body').inner_text()
            info = {'url': page.url, 'body': dom, 'page_errors': page_errors, 'failed_requests': failed,
                'editors': await page.locator('textarea,input,[contenteditable]').evaluate_all("es=>es.map(e=>({tag:e.tagName,id:e.id,type:e.type,placeholder:e.getAttribute('placeholder'),role:e.getAttribute('role'),editable:e.getAttribute('contenteditable')}))"),
                'buttons': await page.locator('button').evaluate_all("es=>es.map(e=>({id:e.id,text:e.textContent,aria:e.getAttribute('aria-label'),title:e.getAttribute('title'),disabled:e.disabled}))"),
                'message_elements': await page.locator('[id*="message"], [class*="message-body"], [class*="prose"]').evaluate_all("es=>es.map(e=>({tag:e.tagName,id:e.id,class:e.className,text:e.innerText?.slice(0,1000)}))")}
            (OUT/'probe.json').write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding='utf8')
            print(json.dumps(info, ensure_ascii=True, indent=2), flush=True)
        finally:
            await browser.close()

asyncio.run(main())
