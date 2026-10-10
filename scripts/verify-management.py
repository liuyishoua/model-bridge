"""Exercise actual upstream model configuration APIs using a disposable alias."""
import json
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://d.58nft.net"

def call(path, payload, key, method="POST"):
    req = urllib.request.Request(BASE + path, data=json.dumps(payload).encode(), method=method, headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r: return r.read()

def main():
    creds = json.loads((ROOT / "data" / "credentials.json").read_text())
    auth = json.loads(call("/api/v1/auths/signin", {"email": creds["admin_email"], "password": creds["admin_password"]}, ""))["token"]
    alias = "leo-management-check:latest"
    payload = {"model": alias, "from": "leo-gpt-oss:20b", "system": "Reply briefly in Chinese.", "parameters": {"temperature": 0.2, "num_ctx": 4096}, "stream": False}
    result = {}
    try:
        call("/ollama/api/create", payload, creds["client_api_key"])
        raise AssertionError("Ordinary API Key unexpectedly created a model")
    except urllib.error.HTTPError as error:
        result["client_management_denied"] = error.code == 403
        assert result["client_management_denied"]
    created = False
    try:
        raw = call("/ollama/api/create/0", payload, auth)
        # Some upstream versions always return NDJSON for management tasks.
        events = [json.loads(line) for line in raw.splitlines() if line]
        assert not any(e.get("error") for e in events), events
        assert events[-1].get("status") == "success", events
        created = True
        result["admin_create_alias"] = True
        shown = json.loads(call("/ollama/api/show", {"model": alias}, auth))
        result["parameters_persisted"] = "0.2" in shown.get("parameters", "") and "4096" in shown.get("parameters", "")
        result["system_prompt_persisted"] = shown.get("system", "") == payload["system"]
        assert result["parameters_persisted"] and result["system_prompt_persisted"]
    finally:
        if created:
            call("/ollama/api/delete/0", {"model": alias}, auth, "DELETE")
            result["disposable_alias_removed"] = True
    path = ROOT / "artifacts" / "management-test.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))

if __name__ == "__main__": main()
