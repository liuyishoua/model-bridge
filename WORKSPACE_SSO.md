# 彩虹桥统一登录（2026-10-27）

网页入口 `https://portal.example.com:20035/` 使用彩虹桥账号和应用权限。中央 `model-bridge` 与 `rift` 均为可申请、可分配、可收回的个人应用。用户、密码、角色与启停在彩虹桥管理；不再在 Open WebUI 创建网页登录密码。

Caddy 全路径校验专用 `ops_workspace_session`，移除调用方提供的全部 `X-Workspace-*` 身份头，再由中央 `/api/auth/access/gate/model-bridge` 返回可信身份。Open WebUI 仅监听回环地址，通过原生 trusted-header sign-in 创建或恢复各自身份。前端在启动应用前完成此步骤，进入时和窗口恢复时重新验证；切换账号清理上一账号的浏览器缓存并重载。

身份由中央用户 ID 稳定映射，不用用户名猜归属。历史账号关联保存在本地 `deploy/workspace-identities.json`，不随源码分发。部署前复制 `deploy/workspace-identities.example.json`，仅添加经核对的关联；没有历史关联时保留空对象。未关联用户使用 `workspace-{id}@bifrost.local`，不会进入其他账号的历史聊天。

`deploy/workspace_sso.py` 阻止应用内注册、改密和账号角色管理，逐请求同步中央角色，原生 JWT 校验同时核对可信邮箱。Socket.IO 的首次连接和 user-join 均校验中央会话及 JWT 归属；存活连接每 15 秒复查，失效、禁用或撤权后断开。新 HTTP 请求由中央即时校验；后台连接复查还受一次最长 4 秒网络验证时间影响。

主动退出只在模型 JWT 与当前中央身份一致时撤销中央会话。旧标签页发现账号已切换时只重新进入当前账号，不能误退出新账号。改密仍由中央现有接口完成，最低 6 个字符，原会话按 auth_version 失效。

独立推理 `/inference/v1/*` 和现有专用 API Key 的模型列表、聊天兼容接口保留原认证；它们不使用浏览器 SSO。Bifrost 域名首页及其他应用路由保持原归属。

## 部署与验证

`WORKSPACE_WEBUI_URL` 必须是浏览器实际入口；示例入口 `https://portal.example.com:20035`，不会继续使用历史公网 IP URL。按原 Compose、Caddy owner 部署。`scripts/prepare-frontend.sh` 生成 `index.workspace.html` 和 `main.workspace.py` 新挂载，避免在准备阶段改写运行中实例的旧挂载。SQLite 备份保留原库、用户 ID 和聊天，不通过覆盖旧备份撤回密码或授权变更。

`tests/workspace_sso_native.py` 在固定镜像中使用临时数据库，验证原生登录、两个账号、私聊隔离、旧 token、角色变化、本地改密禁用、旧标签页退出、中央退出及 Socket.IO 撤权。脚本需要容器内 `/tmp/workspace-sso-qa/workspace_sso.py`，以 `PYTHONPATH=/app/backend` 运行；不读取生产账号、密码或会话。

完整浏览器验收使用独立临时 Open WebUI 容器和临时中央库，验证手机自动登录、账号切换、聊天隔离、权限收回及退出。未调用模型、未使用生产账号。

旧部署验收文档中独立账号登录和应用内建用户的描述属于历史记录，以本文为准。
