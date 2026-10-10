"""Verify the real public -> cloud -> Tailscale -> GPU path, including streaming."""
import argparse
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def request(base, path, key=None, payload=None):
    headers = {"Content-Type": "application/json"}
    if key: headers["Authorization"] = "Bearer " + key
    body = json.dumps(payload).encode() if payload is not None else None
    return urllib.request.urlopen(urllib.request.Request(base + path, data=body, headers=headers), timeout=600)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="https://d.58nft.net")
    parser.add_argument("--model", default="leo-gpt-oss:20b")
    args = parser.parse_args()
    credentials = json.loads((ROOT / "data" / "credentials.json").read_text())
    key = credentials["client_api_key"]
    result = {"base": args.base, "model": args.model, "checked_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "checks": {}}
    checks = result["checks"]
    for label, path, k, expected in [
        ("anonymous_access_denied", "/v1/models", None, 401),
        ("client_admin_access_denied", "/api/v1/users/default/permissions", key, 403),
    ]:
        try:
            with request(args.base, path, k) as r: actual = r.status
        except urllib.error.HTTPError as e: actual = e.code
        checks[label] = {"ok": actual == expected, "http_status": actual}
        assert actual == expected, label
    with request(args.base, "/v1/models", key) as r: models = json.load(r)
    ids = [m["id"] for m in models["data"]]
    checks["model_list"] = {"ok": args.model in ids, "models": ids}
    assert args.model in ids
    payload = {"model": args.model, "messages": [{"role": "user", "content": "请用中文简短回答：17乘以19等于多少？"}], "max_tokens": 256, "temperature": 0, "reasoning_effort": "low", "stream": False}
    started = time.monotonic()
    with request(args.base, "/v1/chat/completions", key, payload) as r: response = json.load(r)
    content = response["choices"][0]["message"].get("content") or ""
    checks["real_inference"] = {"ok": "323" in content, "seconds": round(time.monotonic() - started, 2), "answer": content, "usage": response.get("usage")}
    assert "323" in content, "Model did not return the expected answer"
    payload["messages"] = [{"role": "user", "content": "请用中文说一句你好。"}]
    payload["stream"] = True
    payload["max_tokens"] = 128
    started = time.monotonic(); first = None; chunks = 0; text = ""; done = False
    with request(args.base, "/v1/chat/completions", key, payload) as r:
        for line in r:
            if not line.startswith(b"data:"): continue
            data = line[5:].strip()
            if data == b"[DONE]": done = True; break
            item = json.loads(data)
            chunks += 1
            if first is None: first = round(time.monotonic() - started, 2)
            for choice in item.get("choices", []): text += choice.get("delta", {}).get("content") or ""
    checks["streaming"] = {"ok": done and bool(text), "first_event_seconds": first, "total_seconds": round(time.monotonic() - started, 2), "events": chunks, "answer": text, "done": done}
    assert done and text
    path = ROOT / "artifacts" / "smoke-test.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__": main()
