#!/usr/bin/env bash
set -euo pipefail
cd /home/ubuntu/leo-project/model-bridge
route=/etc/caddy/acli.d/routes/leo-model-bridge.caddy
if [ ! -e backups/model-route-before-client-api.caddy ]; then
    sudo cp "$route" backups/model-route-before-client-api.caddy
    sudo chmod 600 backups/model-route-before-client-api.caddy
fi
python3 - <<'PY'
from pathlib import Path
import subprocess
source = subprocess.check_output(['sudo','cat','/etc/caddy/acli.d/routes/leo-model-bridge.caddy'],text=True)
block = '''# Independent inference API; authenticated by the Windows model host.
@leo_host_inference path /inference/v1/*
handle @leo_host_inference {
    uri strip_prefix /inference
    request_body {
        max_size 8MB
    }
    reverse_proxy http://100.70.120.18:8789 {
        flush_interval -1
        transport http {
            response_header_timeout 600s
        }
    }
}

'''
if '@leo_host_inference' not in source:
    source = block + source
Path('deploy/model-route.caddy').write_text(source)
PY
manager=$(find /usr/local/lib/acli/specs -path '*/lib/acli_caddy_manager.sh' | sort -V | tail -n 1)
test -n "$manager"
sudo bash -c 'source "$1"; acli_caddy_route_put leo-model-bridge "$2"' _ "$manager" "$PWD/deploy/model-route.caddy"
echo 'Client API route installed.'
