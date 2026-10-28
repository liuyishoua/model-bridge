# model-bridge

> 文档中的 example.com 域名、192.0.2.* 地址、/opt/operator 路径及 20000 段端口均为示例，请按实际部署配置替换。私有账号配置与运行数据不随源码提交。

[![License: PolyForm Noncommercial 1.0.0](https://img.shields.io/badge/License-PolyForm%20Noncommercial%201.0.0-orange)](LICENSE)

云端模型网页和 API 入口，通过彩虹桥统一账号、应用授权、Caddy HTTPS 路由连接 Open WebUI 与 GPU 主机。
本仓库保存自有桥接、部署和验证代码；模型权重、聊天记录、账号密钥与第三方镜像不进入 Git。

## 架构

浏览器 → Caddy → Open WebUI → GPU 主机认证网关 → Ollama。
模型与 GPU 推理运行在你自己的主机，云端提供网页、认证和持久聊天历史。
网页由彩虹桥授权后自动登录各自的 Open WebUI 身份；现有模型 API 路径和专用 API Key 保留。账号密码、角色与应用使用权在彩虹桥管理。

统一登录实现和验收见 [WORKSPACE_SSO.md](WORKSPACE_SSO.md)。

## 部署启动

先准备 **Docker Compose、Caddy 和可访问的 GPU 主机**：

```bash
git clone https://github.com/liuyishoua/model-bridge.git
cd model-bridge
cp deploy/cloud.env.example deploy/cloud.env
```

在私有 `deploy/cloud.env` 中填写自己的域名、主机入口和随机密钥，固定已验证的 Open WebUI 镜像 digest。
按 [部署说明](DEPLOYMENT.md) 准备前端挂载文件、TLS 和路由，再运行：

```bash
cd deploy
sudo docker compose --env-file cloud.env -f compose.yaml config --quiet
sudo docker compose --env-file cloud.env -f compose.yaml up -d
```

运行前需完成 GPU 主机与认证网关配置；此项目没有离线演示模式。
不要直接照搬历史部署文档中的域名、私网地址、账号或模型 ID。

## 数据与备份

- `deploy/data/`：Open WebUI 用户与聊天历史。
- `deploy/cloud.env`、`.runtime/`、`backups/`：私有凭据、状态与备份，忽略 Git。
- 模型权重留在 GPU 主机；镜像通过 Docker 获取，不复制第三方应用源码到本仓库。
- 备份、恢复和诊断见 原部署说明（本地资料）。

## 验证

```bash
python3 -m unittest discover -s test -p 'test_*.py'
```

本地测试覆盖桥接协议；涉及 SDK、网页和真实模型的脚本会使用已配置的服务，按各脚本说明单独运行。

## 目录

- `src/`：模型桥接服务；`deploy/`：云端部署模板和脚本。
- `scripts/`：安装、管理、备份与诊断工具；`test/`：协议测试。
- `web/`、`examples/`、`openapi.json`：网页资源与客户端接口示例。

## 使用许可

**本项目仅供学习、研究、测试及其他非商业用途，不得用于商业目的。**
对本仓库中版权所有者拥有权利的代码，采用
[PolyForm Noncommercial License 1.0.0](LICENSE)；商业使用须事先取得版权所有者的单独授权。
本项目属于**源码可见、限制商用**，不应标为 MIT 或 OSI 意义上的开源许可证。

第三方代码、素材和依赖仍受其各自许可条件约束，来源与许可范围见
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。本声明不追溯改变第三方代码或此前已发布版本的许可。

## 本地身份关联配置

首次部署前将 `deploy/workspace-identities.example.json` 复制为 `deploy/workspace-identities.json`。空对象表示没有旧账号关联；历史用户映射只在本地填写。该私有配置不提交，业务源码与实际部署使用同一套。

## 原生前端缓存

`deploy/frontend-cache.caddy` 为带内容指纹的 `/_app/immutable/` 脚本、样式等资源启用压缩与长期缓存，仅处理成功的静态响应。将该片段导入模型网页的代理处理块；保留原有统一身份校验。HTML、登录失败和聊天 API 不适用该缓存策略。
