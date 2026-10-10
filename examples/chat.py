"""Set LEO_API_KEY, then run this file. Uses the standard Chat Completions path."""
import json
import os
import urllib.request

base = os.environ.get("LEO_MODEL_URL", "https://d.58nft.net")
key = os.environ["LEO_API_KEY"]
body = json.dumps({"model": "leo-gpt-oss:20b", "messages": [{"role": "user", "content": "用中文介绍一下你能做什么。"}], "stream": True, "max_tokens": 512}).encode()
req = urllib.request.Request(base + "/v1/chat/completions", data=body, headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
with urllib.request.urlopen(req, timeout=600) as response:
    for line in response:
        if not line.startswith(b"data:"): continue
        data = line[5:].strip()
        if data == b"[DONE]": break
        event = json.loads(data)
        for choice in event.get("choices", []):
            content = choice.get("delta", {}).get("content")
            if content: print(content, end="", flush=True)
print()
