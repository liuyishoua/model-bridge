"""Use upstream Open WebUI APIs to bootstrap and inspect this installation.
Never print login tokens, API keys or passwords to the terminal.
"""
import argparse
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def call(base, path, payload=None, bearer=None, method=None):
    headers = {"Content-Type": "application/json"}
    if bearer: headers["Authorization"] = "Bearer " + bearer
    raw = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(base + path, data=raw, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=60) as response: return json.load(response)

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--base", default="https://d.58nft.net")
    p.add_argument("--credentials", default=str(ROOT / "data" / "credentials.json"))
    p.add_argument("--create-client", action="store_true")
    p.add_argument("--publish-model", action="store_true", help="Allow authenticated users to read the base model")
    p.add_argument("--configure-chat", action="store_true", help="Disable automatic built-in tools for the 4096-token chat model")
    args = p.parse_args()
    creds_path = Path(args.credentials)
    creds = json.loads(creds_path.read_text())
    admin = call(args.base, "/api/v1/auths/signin", {"email": creds["admin_email"], "password": creds["admin_password"]})
    auth = admin["token"]
    result = {"admin_login": True}
    result["models"] = [m["id"] for m in call(args.base, "/api/models", bearer=auth)["data"]]
    if args.publish_model:
        call(args.base, "/api/v1/models/model/access/update", {
            "id": "leo-gpt-oss:20b", "name": "Leo GPT OSS 20B",
            "access_grants": [{"principal_type": "user", "principal_id": "*", "permission": "read"}],
        }, bearer=auth)
        result["model_available_to_authenticated_users"] = True
    if args.configure_chat:
        model = call(args.base, "/api/v1/models/model?id=leo-gpt-oss%3A20b", bearer=auth)
        # v0.11.4 injects 35 built-in tools by default into browser sessions.
        # Their schemas overflow this GPU's 4096-token context and cause Ollama
        # to truncate conversation history. Use upstream per-model settings.
        meta = model.get("meta") or {}
        capabilities = meta.get("capabilities") or {}
        capabilities["builtin_tools"] = False
        meta["capabilities"] = capabilities
        payload = {key: model[key] for key in ("id", "name", "base_model_id", "params", "is_active", "access_grants") if key in model}
        payload["meta"] = meta
        saved = call(args.base, "/api/v1/models/model/update", payload, bearer=auth)
        assert saved["meta"]["capabilities"]["builtin_tools"] is False
        result["automatic_builtin_tools_disabled"] = True
    if args.create_client and not creds.get("client_email"):
        import secrets
        password = secrets.token_urlsafe(24)
        client = call(args.base, "/api/v1/auths/add", {"name": "Leo API Client", "email": "api@model.local", "password": password, "role": "user"}, bearer=auth)
        creds["client_email"] = "api@model.local"
        creds["client_password"] = password
        creds["client_id"] = client["id"]
        creds_path.write_text(json.dumps(creds, indent=2))
        result["client_created"] = True
    if args.create_client:
        permissions = call(args.base, "/api/v1/users/default/permissions", bearer=auth)
        permissions["features"]["api_keys"] = True
        permissions["features"]["direct_tool_servers"] = False
        for key in permissions["workspace"]:
            if isinstance(permissions["workspace"][key], bool): permissions["workspace"][key] = False
        call(args.base, "/api/v1/users/default/permissions", permissions, bearer=auth)
        client = call(args.base, "/api/v1/auths/signin", {"email": creds["client_email"], "password": creds["client_password"]})
        if not creds.get("client_api_key"):
            creds["client_api_key"] = call(args.base, "/api/v1/auths/api_key", {}, bearer=client["token"])["api_key"]
            creds_path.write_text(json.dumps(creds, indent=2))
        result["client_api_key_ready"] = True
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == "__main__": main()
