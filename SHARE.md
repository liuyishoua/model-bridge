# 模型服务使用说明

服务地址：[https://d.58nft.net](https://d.58nft.net)。可以从联网电脑、手机的浏览器打开，不需要安装 Ollama 或 Tailscale。

原 IP 入口 `https://43.172.70.56` 仍可使用。

## 网页聊天

1. 联系服务管理员领取自己的账号和初始密码。
2. 打开服务地址并登录，选择 `leo-gpt-oss:20b` 开始聊天。
3. 首次登录后，在账号设置中修改自己的密码。

当前不开放自行注册。管理员在管理面板的用户页面为每位使用者添加普通用户账号；基础模型已向登录用户开放读取。普通用户可以聊天，管理员负责模型配置和用户管理。

## 程序调用

登录网页，在账号设置中生成自己的 API Key。应用配置填写：

| 配置项 | 内容 |
| --- | --- |
| 接口类型 | OpenAI 兼容 Chat Completions |
| Base URL | `https://d.58nft.net/v1` |
| 模型 | `leo-gpt-oss:20b` |
| API Key | 自己账号生成的 Key |

支持模型列表和聊天接口，聊天可使用流式输出。

```python
import os
from openai import OpenAI

client = OpenAI(
    base_url="https://d.58nft.net/v1",
    api_key=os.environ["LEO_API_KEY"],
)
response = client.chat.completions.create(
    model="leo-gpt-oss:20b",
    messages=[{"role": "user", "content": "请用中文介绍一下自己。"}],
    reasoning_effort="low",
    max_tokens=512,
)
print(response.choices[0].message.content)
```

OpenAPI 描述：[https://d.58nft.net/openapi.json](https://d.58nft.net/openapi.json)。

## 使用条件

模型运行在管理员的 GPU 主机上。主机开机联网时可以使用；模型首次加载需要额外等待。当前一次处理一个推理请求，忙时可排队等待；队列满或等待超时会返回 429，请稍后重试。

此说明可以转发给其他使用者；账号密码和 API Key 单独分配。管理员自己的凭证文件包含后台及主机连接凭证，应由管理员保管。
