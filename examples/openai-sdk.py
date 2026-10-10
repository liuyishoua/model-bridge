"""pip install openai; set LEO_API_KEY before running."""
import os
from openai import OpenAI

client = OpenAI(base_url=os.environ.get("LEO_MODEL_URL", "https://d.58nft.net") + "/v1", api_key=os.environ["LEO_API_KEY"], timeout=600)
for event in client.chat.completions.create(model="leo-gpt-oss:20b", messages=[{"role": "user", "content": "请用中文介绍你的能力。"}], max_tokens=512, stream=True):
    if event.choices and event.choices[0].delta.content: print(event.choices[0].delta.content, end="", flush=True)
print()
