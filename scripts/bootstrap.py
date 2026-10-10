"""Generate private configuration once; reruns do not rotate secrets."""
import json
import os
import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
data = ROOT / "data"
data.mkdir(exist_ok=True)
env_path = ROOT / ".env"
cloud_path = ROOT / "deploy" / "cloud.env"
credentials = data / "credentials.json"
if not credentials.exists():
    credentials.write_text(json.dumps({"admin_email": "leo@model.local", "admin_password": secrets.token_urlsafe(24), "webui_secret": secrets.token_hex(32), "bridge_token": secrets.token_urlsafe(48)}, indent=2), encoding="utf-8")
    os.chmod(credentials, 0o600)
values = json.loads(credentials.read_text())
if not env_path.exists():
    env_path.write_text((ROOT / ".env.example").read_text().replace("replace-with-a-long-random-token", values["bridge_token"]), encoding="utf-8")
    os.chmod(env_path, 0o600)
if not cloud_path.exists():
    cloud_path.parent.mkdir(exist_ok=True)
    cloud_path.write_text("\n".join([
        "WEBUI_IMAGE=ghcr.io/open-webui/open-webui@sha256:e8adae70e1db7a838d5d6cdfe2a66a4c1d293a0361b304ccc20df179b17aeead",
        "WEBUI_PORT=8788", "WEBUI_URL=https://d.58nft.net", "HOST_BRIDGE_URL=http://100.70.120.18:8787",
        "BRIDGE_TOKEN=" + values["bridge_token"], "WEBUI_SECRET_KEY=" + values["webui_secret"],
        "WEBUI_ADMIN_EMAIL=" + values["admin_email"], "WEBUI_ADMIN_PASSWORD=" + values["admin_password"],
    ]) + "\n", encoding="utf-8")
    os.chmod(cloud_path, 0o600)
print("Configuration ready. Private credentials:", credentials)
