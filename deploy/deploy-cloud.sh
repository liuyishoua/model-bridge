#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
test -f cloud.env || { echo 'Upload private cloud.env first'; exit 1; }
chmod 600 cloud.env
mkdir -p data
sudo docker compose --env-file cloud.env -f compose.yaml config --quiet
bash ../scripts/prepare-frontend.sh
sudo docker compose --env-file cloud.env -f compose.yaml up -d
for attempt in $(seq 1 60); do
    if curl -fsS http://127.0.0.1:8788/health >/dev/null; then break; fi
    sleep 2
done
curl -fsS http://127.0.0.1:8788/health
sudo install -d -m 755 /var/lib/leo-model-bridge
sudo install -m 644 ../openapi.json /var/lib/leo-model-bridge/openapi.json
sudo install -m 644 ../web/login.html /var/lib/leo-model-bridge/login.html
sudo install -m 644 ../web/auth-redirect.js /var/lib/leo-model-bridge/auth-redirect.js
# The host already has a shared Caddy config manager. Keep other owners intact.
manager=$(find /usr/local/lib/acli/specs -path '*/lib/acli_caddy_manager.sh' | sort -V | tail -n 1)
test -n "$manager" || { echo 'Shared Caddy manager not found; install model.caddy separately'; exit 1; }
sudo bash -c 'source "$1"; acli_caddy_route_put leo-model-bridge "$2"' _ "$manager" "$PWD/model-route.caddy"
if [ -f model-domain.caddy ]; then
    domain_owner=$(cat model-domain.owner)
    case "$domain_owner" in leo-model-bridge|d.58nft.net) ;; *) echo 'Unexpected domain owner'; exit 1 ;; esac
    sudo bash -c 'source "$1"; acli_caddy_site_put "$2" "$3"' _ "$manager" "$domain_owner" "$PWD/model-domain.caddy"
fi
echo 'Cloud model service deployed at https://43.172.70.56'
