from pathlib import Path

path = Path('/home/ubuntu/leo-project/model-bridge/scripts/diagnose-cloud.py')
source = path.read_text()
old = 'data = {"requests": data["requests"], "download": {k: data["download"].get(k) for k in ["complete", "downloaded", "total", "percent"]}}'
new = 'data = {"requests": data["requests"], "storage": data.get("storage", {})}'
if old in source:
    path.write_text(source.replace(old, new))
print('Cloud diagnostics updated for model host storage status.')
