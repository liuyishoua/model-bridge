#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
manager=$(find /usr/local/lib/acli/specs -path '*/lib/acli_caddy_manager.sh' | sort -V | tail -n 1)
if [ -f model-domain.owner ] && [ "$(cat model-domain.owner)" = "d.58nft.net" ]; then
    test -f ../backups/d-domain-original.caddy
    sudo bash -c 'source "$1"; acli_caddy_site_put d.58nft.net "$2"' _ "$manager" "$PWD/../backups/d-domain-original.caddy"
fi
sudo bash -c 'source "$1"; acli_caddy_owner_remove leo-model-bridge' _ "$manager"
sudo docker compose --env-file cloud.env -f compose.yaml stop
echo 'Model gateway stopped. Persistent user data and other projects are retained.'
