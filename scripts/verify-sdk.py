"""Validate a real external OpenAI SDK client against the deployed endpoint."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".runtime" / "client-python"))
from openai import OpenAI

def main():
    c = json.loads((ROOT / "data" / "credentials.json").read_text())
    client = OpenAI(base_url="https://d.58nft.net/v1", api_key=c["client_api_key"], timeout=600, max_retries=0)
    ids = [m.id for m in client.models.list()]
    assert "leo-gpt-oss:20b" in ids
    reply = client.chat.completions.create(model="leo-gpt-oss:20b", messages=[{"role": "user", "content": "Reply with the word READY."}], max_tokens=128, reasoning_effort="low")
    answer = reply.choices[0].message.content or ""
    assert "READY" in answer.upper(), answer
    result = {"sdk_model_list": True, "sdk_chat_completion": True, "answer": answer, "usage": reply.usage.model_dump() if reply.usage else None}
    (ROOT / "artifacts").mkdir(exist_ok=True)
    (ROOT / "artifacts" / "sdk-test.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == "__main__": main()
