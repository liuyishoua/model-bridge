import json
import urllib.request
from pathlib import Path

root = Path(__file__).resolve().parents[1]
env = dict(line.split("=", 1) for line in (root / "deploy" / "cloud.env").read_text().splitlines() if line and not line.startswith("#"))
checks = [
    ("webui_health", "http://127.0.0.1:8788/health", None),
    ("host_bridge", env["HOST_BRIDGE_URL"] + "/bridge/status", env["BRIDGE_TOKEN"]),
    ("ollama_models", env["HOST_BRIDGE_URL"] + "/api/tags", env["BRIDGE_TOKEN"]),
]
for name, url, key in checks:
    headers = {"Authorization": "Bearer " + key} if key else {}
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as r: data = json.load(r)
        if name == "host_bridge": data = {"requests": data["requests"], "storage": data.get("storage", {})}
        print(json.dumps({"check": name, "ok": True, "data": data}))
    except Exception as e: print(json.dumps({"check": name, "ok": False, "error": str(e)}))
