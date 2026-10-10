#!/usr/bin/env bash
set -euo pipefail
project=$(cd "$(dirname "$0")/.." && pwd)
cd "$project/deploy"
mkdir -p frontend
image=$(sudo docker compose --env-file cloud.env -f compose.yaml config --images)
sudo docker image inspect "$image" >/dev/null 2>&1 || sudo docker pull "$image"
container=$(sudo docker create --entrypoint /bin/true "$image")
trap 'sudo docker rm -f "$container" >/dev/null' EXIT
sudo docker cp "$container:/app/build/index.html" frontend/index.upstream.html
sudo docker cp "$container:/app/backend/open_webui/main.py" frontend/main.upstream.py
sudo chown "$(id -u):$(id -g)" frontend/index.upstream.html
sudo chown "$(id -u):$(id -g)" frontend/main.upstream.py
python3 - <<'PY'
from pathlib import Path
source = Path('frontend/index.upstream.html').read_text(encoding='utf-8')
assert source.count('</head>') == 1, 'Upstream HTML layout changed; review before deploying'
script = '<script src="/leo-auth-redirect.js?v=1"></script>\n'
Path('frontend/index.html').write_text(source.replace('</head>', script + '</head>'), encoding='utf-8')
# v0.11.4 initial-title context omits model, but memory review reads ctx['model'].
# Keep this one-field compatibility fix explicit and fail if upstream changes.
backend = Path('frontend/main.upstream.py').read_text(encoding='utf-8')
anchor = 'title_ctx = {\n'
assert backend.count(anchor) == 1, 'Upstream title context changed; review the compatibility fix'
backend = backend.replace(anchor, anchor + "                            'model': model,\n")
compile(backend, 'main.py', 'exec')
Path('frontend/main.py').write_text(backend, encoding='utf-8')
PY
chmod 644 frontend/index.html frontend/main.py
