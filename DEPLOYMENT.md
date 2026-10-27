# 部署与验收记录

当前网页入口：`https://d.58nft.net:9449/`，已接入 Bifrost 应用列表。`https://d.58nft.net/` 首页归 Bifrost 门户；原域名 `/v1/*`、`/inference/v1/*` API 路由保留。原模型域名接管配置已移为 `deploy/model-domain.*.before-bifrost`，防止模型重部署覆盖门户首页。当前独立模型站点配置为 `deploy/model-domain.caddy`，owner 为 `leo-model-bridge`，仅使用端口 9449。下文保留此前验收记录，历史域名说明不代表当前首页归属。

当前网页登录规则已更新为 [彩虹桥统一登录](WORKSPACE_SSO.md)。下文 2026-10-05 的独立密码与应用内创建用户说明仅为历史验收记录。

验收时间：2026-10-05，Asia/Shanghai。

## 直接使用

- 网页：[https://d.58nft.net:9449/](https://d.58nft.net:9449/)。
- API Base URL：`https://d.58nft.net/v1`
- 模型 ID：`leo-gpt-oss:20b`
- 管理员登录账号：`leo`；普通聊天/API 用户：`api@model.local`。
- 简洁登录入口：[https://d.58nft.net:9449/login](https://d.58nft.net:9449/login)。管理员已按要求更新密码；当前密码见本机凭证文件。
- 密码和普通用户 API Key：本机 `E:\leo-project\model-bridge\data\credentials.json`。不要把该文件加入 Git 或发给其他使用者。
- 管理员登录后可添加其他账号。默认关闭自行注册；基础模型已授予登录用户读取权限。
- 模型配置入口与 API 示例见 [README](README.md)。

## 实际链路

```text
公网 HTTPS :443
  → leo-ubuntu 现有 Caddy（独立 owner leo-model-bridge）
  → Open WebUI 容器（服务器回环地址 :8788）
  → Tailscale 100.70.120.18:8787
  → 本机认证桥接器（回环地址 :8787）
  → Ollama（回环地址 :11434）
  → RTX 3080 Laptop / CUDA / gpt-oss-20b
```

海外服务器提供账号、聊天历史和公网 API，本机保存权重并推理。调用方只需要网页账号或 API Key，不需要安装 Tailscale。两端的 Tailscale 连接验收时经过 DERP 中继，网络首跳延迟约 225 ms。

## 验收结果

| 项目 | 实测结果 |
| --- | --- |
| 公网 HTTPS 页面、OpenAPI 描述 | 200，证书正常校验 |
| 云端容器 | Open WebUI v0.11.4，healthy，约 326 MiB 内存 |
| 云端到本机私网 | 健康检查、下载状态、模型列表均成功 |
| 无凭证调用模型列表 | 401 |
| 普通 API Key 访问管理接口 | 403 |
| 普通 API Key 模型列表 | 包含 `leo-gpt-oss:20b` |
| 实际数学推理 | `17 × 19` 返回 `323` |
| 中文 SSE 流式输出 | 返回“你好！”，52 个事件，正常收到 `[DONE]` |
| 真实 OpenAI Python SDK | models.list 与 chat.completions 均通过，回答 `READY` |
| 管理员远程模型配置 | 创建临时别名，提示词、temperature=0.2、num_ctx=4096 持久化成功 |
| 临时测试模型清理 | 已删除，仅保留正式模型 |
| 桥接器测试 | 8 项通过：认证、路由、JSON、流式、并发、等待队列、下载状态和配置边界 |
| 原有域名服务 | `d.58nft.net` 保持原有 302 行为 |
| 数据备份 | 已实际完成备份并自动恢复容器，恢复后 healthy、管理员登录成功 |

详细结果保存在本机 [smoke-test.json](artifacts/smoke-test.json)、[management-test.json](artifacts/management-test.json)、[sdk-test.json](artifacts/sdk-test.json)。这些文件不包含访问凭证。

首次数学请求经过完整公网链路耗时 16.55 秒，其中模型加载 13.82 秒。随后的中文流式请求首事件 1.3 秒、总耗时 2.0 秒；首事件可能属于模型思考阶段。两次短请求报告的生成速度约 77–80 token/s，不能据此承诺所有长对话或多用户的速度。

Ollama `ps` 显示 `100% GPU`、上下文 4096；日志显示 25/25 层卸载到 CUDA，GPU 权重缓冲约 12,037 MiB。同一时刻执行一个推理请求，另允许 4 个请求等待，最长等待 120 秒；队列满或等待超时返回 429。

08:49补充完成真实 Chromium 浏览器逐项点击和视觉验收：管理员、普通用户、手机尺寸与桌面尺寸均可登录、输入问题、显示正确回复并保存历史。包括连续追问与完整乘法表，详细证据见 [公网网页验收](BROWSER_ACCEPTANCE.md)。

## 文件与模型

原始模型位于 `E:\leo-project\models\gpt-oss-20b`，原下载程序记录全部文件完成并通过 SHA 校验，总计 13,789,264,674 字节，约 13.79 GB。

- 原始权重：3 个 Safetensors 分片，以及 tokenizer、配置、索引和许可证。
- 转换输出：`data/converted/gpt-oss-20b-mxfp4.gguf`，13,792,638,720 字节。
- Ollama 存储：`data/ollama-models/`。
- 运行日志：`data/logs/`；转换及导入日志：`data/conversion.log`、`data/import.log`。
- 开源版本、镜像 digest、GGUF SHA 和转换器提交见 [sources.lock.json](sources.lock.json)。

转换使用 llama.cpp 官方工具，保留 MXFP4 专家量化；对话模板复用 Ollama 官方 gpt-oss Harmony 模板。原始文件、转换文件、Ollama 存储各保留一份，便于恢复，目前未做磁盘去重。

## 运行条件

当前 Windows 用户登录后通过 Startup 快捷方式启动服务。桥接器运行期间阻止系统自动闲置休眠；关机、主动休眠、断网或退出服务仍会中断推理。云端容器配置自动重启。

服务支持网页聊天、用户管理、模型配置和两个公开兼容端点：模型列表、Chat Completions。知识库、语音、联网检索没有配置。当前没有接入 Bifrost，也没有单独增加多模型网关。

云端目录：`/home/ubuntu/leo-project/model-bridge`。`scripts/backup-cloud.sh` 会短暂停止本项目容器、备份用户数据与配置并自动启动；回退脚本只移除本项目路由和容器，保留数据。

本次备份位于云端 `backups/model-webui-20261004T182530Z.tar.gz`，文件权限 600。

## 公网开放复验

2026-10-05 02:37（Asia/Shanghai），再次确认 `leo-ubuntu` 容器 healthy，云端到本机模型连接正常。从云端运行客户端，直接访问公网 `https://43.172.70.56`，通过正常 HTTPS 证书校验：页面、OpenAPI、普通用户模型列表均成功；匿名 API 请求被拒绝。普通用户 Key 的实际推理返回 `323`，包含模型重新加载共耗时 13.26 秒。

此次结果保存在本机 [cloud-public-test.json](artifacts/cloud-public-test.json)。这次复验的客户端运行在云端，未使用独立第三方电脑做浏览器点击测试。

其他用户的账号由管理员在用户管理页面添加；每人使用自己的账号和 API Key。可转发的无凭证说明见 [SHARE.md](SHARE.md)。

管理员简洁登录已验证：登录页将 `leo` 映射到原有管理员身份，认证和权限仍由 Open WebUI 处理；新密码登录成功，角色为 `admin`，会话 Cookie 可打开主界面，管理员模型列表包含正式模型。其他用户仍可用自己的邮箱登录。

## 网页发送消息修复

2026-10-05 02:56（Asia/Shanghai），修复网页初始标题生成与正文推理并发时被单请求限制立即返回 429 的问题。仍然保持 GPU 单个推理任务运行，新增有界等待；桥接器 8 项测试通过。

管理员完整聊天协议测试已通过公网 HTTPS 和 WebSocket：创建会话、流式回答、自动标题、标签、后续问题生成以及消息持久化均成功。回答为 `323`，标题为 `Math Question`，完整流程耗时 12.66 秒。测试创建的临时会话已删除。结果见 [web-chat-test.json](artifacts/web-chat-test.json)。该测试覆盖真实网页网络协议，没有执行浏览器视觉点击测试。

同时补齐旧会话失效后的前端 `/auth` 跳转，统一进入支持 `leo` 的简洁登录页。

03:01 复验：已补齐上游初始标题任务上下文的 `model` 字段，修复记忆检查的 `KeyError`。重新执行完整管理员聊天协议测试，标题为 `Multiplication Problem`，回答 `323`，流式、标签、后续问题、保存及测试会话删除均成功，耗时 13.69 秒；新容器日志未出现上述错误，容器 healthy。兼容修改由部署脚本从固定镜像生成并只读挂载。

08:41–08:52补充修复浏览器连续追问：上游默认35个内置工具说明超过本机上下文容量，导致Ollama截断输入；通过上游每模型配置关闭自动内置工具。真实网页三组会话、共六个问题均通过，页面显示323、330、31支、33支、完整正确乘法表以及中文科普回复，刷新后历史保留。8项桥接器测试再次通过。

## 正式域名切换

2026-10-05 09:00，用户明确同意将 `d.58nft.net` 从 Bifrost 门户切换给 Open WebUI。DNS已经指向43.172.70.56，无需新增记录。使用共享Caddy管理器验证并原子替换原 `d.58nft.net` site owner，导入本项目路由，证书正常校验；模型原IP入口继续200，Bifrost原IP:9443入口继续302到其登录页，相关进程未停止。

原域名配置备份：云端 `backups/d-domain-original.caddy`。正式站点记录：`deploy/model-domain.caddy` 与 `deploy/model-domain.owner`，均在云端保存，生成文件不加入Git。`deploy/deploy-cloud.sh` 会沿用域名配置；`deploy/rollback-cloud.sh` 会先恢复原Bifrost域名路由，再撤销模型服务。云端环境文件和持久化 `webui.url` 已更新为 `https://d.58nft.net`，原有账号、密码和权限保留。

09:00–09:03，新域名三组浏览器会话、六个真实页面问题全部通过，涵盖管理员和普通账号、手机和桌面尺寸、连续追问、表格、中文回答和刷新后历史保存。截图和报告见 `artifacts/browser/20261005T090031-426d9818/`。域名API的认证边界、模型列表、真实数学推理和SSE流式复验也全部通过；模型返回323耗时2.03秒，流式58个事件正常结束。详细说明见 [公网网页验收](BROWSER_ACCEPTANCE.md)。
