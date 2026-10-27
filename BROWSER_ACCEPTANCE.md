# 公网网页验收

2026-10-05 08:49–08:52，Asia/Shanghai。使用云端独立 Linux Chromium 浏览器，经过公网 `https://43.172.70.56`，正常校验 HTTPS 证书。手机尺寸 430×900、桌面尺寸 1280×900，测试管理员 `leo` 与普通账号。所有问题都在真实页面输入并点击发送，没有直接调用聊天 API，也没有模拟模型返回。

## 实际结果

| 页面与账号 | 输入与实际可见输出 | 结果 |
| --- | --- | --- |
| 手机尺寸，管理员 | 17×19 → **323**；追问再加7 → **330** | 通过 |
| 手机尺寸，管理员 | 17×1 到 17×9 的 Markdown 表格，逐行核对全部9行 | 通过 |
| 手机尺寸，普通用户 | 3盒×12支−5支 → **31支**；追问再买2支 → **33支** | 通过 |
| 桌面尺寸，普通用户 | 中文解释蓝色天空，页面回答包含短波蓝光被大气分子更强地散射 | 通过 |
| 三个独立会话 | 刷新页面后答案仍在；无页面 JavaScript 异常 | 通过 |
| 网页实际网络 | 六次聊天请求均200，使用 `leo-gpt-oss:20b`；收到真实 WebSocket 流式事件 | 通过 |

此次可见答案出现时间为1.38–7.61秒，含后台标题和追问任务的完成时间为8.82–22.58秒；这组短问题的耗时不代表长会话或多人同时请求的速度。

报告与真实截图位于 `artifacts/browser/20261005T084847-c85b9ccc/`，均不含访问密钥。管理员成功会话保留在 [网页会话](https://43.172.70.56/c/16740890-6fa2-4d28-b535-0d1ad15e8399)，登录 `leo` 后可查看。此测试覆盖真实浏览器和公网链路，手机尺寸由 Chromium 模拟，没有声称测试过实体 Android 手机。

![普通用户连续对话](artifacts/browser/20261005T084847-c85b9ccc/user-mobile-reloaded.png)

## 修复原因

先前仅检查单次推理和网页网络协议，遗漏了浏览器连续追问。实际页面复现了首问323、追问25或22甚至“不确定”的问题。

Open WebUI v0.11.4 默认给浏览器会话加入35个内置工具，工具说明挤占本机4096-token上下文。Ollama日志显示 `truncating input prompt`，原提示词约4099–4100 tokens，被进一步截至2050 tokens；历史记录虽保存正确，但模型输入被截断。对同一实际请求做对照，保留工具答错，去掉工具返回330。

通过上游模型配置接口将 `meta.capabilities.builtin_tools` 设为 `false`，停止对普通聊天自动注入这些工具。保留原模型、Harmony模板、历史记录和管理员配置能力。配置在云端数据库中持久化；不是给测试问题硬编码答案。

## 复验

```powershell
D:\anaconda\python.exe scripts\cloud-admin.py --configure-chat
D:\anaconda\python.exe scripts\run-browser-test.py
# 域名接通后也可验证对应入口：
D:\anaconda\python.exe scripts\run-browser-test.py --base https://portal.example.com
```

`run-browser-test.py` 在 leo-ubuntu 上使用固定版本的 [Playwright 官方 Docker 环境](https://playwright.dev/python/docs/docker)。首次需要下载浏览器镜像，后续复用。登录凭证只暂存为服务器权限600的独立文件，执行完成或失败后删除；报告与截图复制回本机 `artifacts/browser/<run-id>/`。测试会话保留供人工检查。

浏览器测试还发现过测试脚本自身对表格文本的断言问题：DOM `textContent` 会拼接相邻单元格，最终改为读取可见 `inner_text` 并逐行核对数值。该问题未改变模型或网页回复。

## 正式域名复验

2026-10-05 09:00–09:03，用户同意将原 Bifrost 域名用途切换后，使用 `https://portal.example.com` 重跑上述三组、六次真实网页交互，全部通过；三个会话刷新后仍有完整答案，无页面脚本异常。新域名的管理员成功会话为 [实际网页会话](https://portal.example.com/c/68986694-0ab3-4f84-87e3-dab0c7db7630)。

结果与截图位于 `artifacts/browser/20261005T090031-426d9818/`。同一新域名的 API 复验通过匿名401、普通用户管理接口403、模型列表、数学323以及58个SSE事件和 `[DONE]`；详见 `artifacts/smoke-test.json`。证书校验正常，原模型 IP 入口200，Bifrost 原 IP:20029 入口保留302登录跳转。
