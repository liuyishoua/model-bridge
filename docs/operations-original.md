# Leo Cloud Model Entry

网页入口：<https://d.58nft.net:9449/>，可从 Bifrost 门户 <https://d.58nft.net/> 的应用列表打开。域名根路径是门户首页；下文的 `/v1` 与 `/inference/v1` 模型 API 地址继续有效。

本目录是 leo-ubuntu 的 Open WebUI / Caddy 部署项目。官方 Open WebUI 镜像运行在 `leo-model-webui` 容器中，用户、配置及聊天历史持久化到 `deploy/data`。当前镜像已按 digest 固定。

## 主机职责

- Windows：`E:\leo-project\model-host` 保存 Ollama 启动、认证网关、客户端 Key 和运行日志。
- Windows：`F:\models` 保存原始权重、转换后的 GGUF 和 Ollama 仓库。
- leo-ubuntu：`/home/ubuntu/leo-project/model-bridge` 保存网页、Caddy 入口和云端部署代码。

Windows 启动代码必须在 GPU 主机运行。云端容器通过 Tailscale HTTP 连接主机，无需启动云端 Ollama，也无需复制权重。

## 两个公网 API

| 入口 | 验证 Key 的位置 | 支持范围 |
| --- | --- | --- |
| `https://d.58nft.net/v1` | Open WebUI 用户系统 | 模型列表、Chat Completions |
| `https://d.58nft.net/inference/v1` | Windows 模型主机 | 模型列表、Chat Completions、无状态 Responses |

网页请求：Caddy → `127.0.0.1:8788` → Open WebUI → Tailscale `100.70.120.18:8787` → Windows 网关 → Ollama。

通用客户端请求：Caddy → Tailscale `100.70.120.18:8789` → Windows 客户端 API → Ollama。客户端入口使用独立 Key，不开放管理接口，也不依赖 Open WebUI 的聊天协议。调用方无需安装 Tailscale。

通用 API 在服务器 `deploy/model-route.caddy` 中维护，`deploy/enable-client-api.sh` 通过现有 Caddy shared manager 验证并应用路由。部署时执行 `deploy/deploy-cloud.sh` 会使用这份路由。添加前的路由备份在 `backups/model-route-before-client-api.caddy`。

## 运维

```bash
cd /home/ubuntu/leo-project/model-bridge/deploy
sudo docker compose --env-file cloud.env -f compose.yaml ps
sudo docker compose --env-file cloud.env -f compose.yaml logs --tail 50
python3 ../scripts/diagnose-cloud.py
```

Ollama 主机必须开机、联网并运行模型服务。两个入口共享主机的 GPU 队列。模型加载、上下文容量及推理能力由本机决定。

完整拆分前的 Windows 云端源码及验收证据已保存在 `backups/windows-cloud-source-before-split.zip`。云端账号信息另存 `backups/windows-credentials.json`，不要将凭证或 `cloud.env` 加入 Git。Windows 上只保留主机凭证和独立客户端 Key。

当前公网 Responses 和流式响应已验收；Codex CLI 0.160.0 通过该公网 Responses 入口完成一次简短请求。该结果不代表长上下文仓库任务已验收。

Open WebUI 使用公开源代码及官方 Docker 镜像：[官方项目](https://github.com/open-webui/open-webui)、[Docker 部署文档](https://docs.openwebui.com/getting-started/quick-start/)。二次分发遵循当前上游许可证中的品牌条款。
