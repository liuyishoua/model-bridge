#!/usr/bin/env bash
# Apply a model-service HTTPS name using the shared, atomic Caddy manager.
set -euo pipefail
cd "$(dirname "$0")"
domain=${1:-d.58nft.net}
mode=${2:-apply}
python3 - "$domain" "$mode" <<'PY'
import re, sys
name = sys.argv[1]
assert len(name) <= 253 and re.fullmatch(r'[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?', name), 'Invalid domain'
assert '.' in name and '..' not in name, 'Invalid domain'
assert sys.argv[2] in ('apply', '--prepare-only', '--replace-existing'), 'Invalid mode'
assert name != 'd.58nft.net' or sys.argv[2] in ('--prepare-only', '--replace-existing'), 'Replacing the existing Bifrost domain requires --replace-existing'
PY
printf 'https://%s {\n    import "/etc/caddy/acli.d/routes/leo-model-bridge.caddy"\n}\n' "$domain" > model-domain.pending.caddy
if [ "$mode" = "--prepare-only" ]; then
    echo "Prepared HTTPS site for $domain; DNS A record must point to 43.172.70.56."
    exit 0
fi
python3 - "$domain" <<'PY'
import socket, sys
name = sys.argv[1]
try:
    addresses = {info[4][0] for info in socket.getaddrinfo(name, 443, type=socket.SOCK_STREAM)}
except socket.gaierror:
    raise SystemExit('DNS is not ready. Add an A record pointing to 43.172.70.56, then retry.')
assert '43.172.70.56' in addresses and addresses <= {'43.172.70.56'}, f'Unexpected DNS addresses: {addresses}'
PY
manager=$(find /usr/local/lib/acli/specs -path '*/lib/acli_caddy_manager.sh' | sort -V | tail -n 1)
test -n "$manager"
owner=leo-model-bridge
if [ "$domain" = "d.58nft.net" ]; then
    owner=d.58nft.net
    mkdir -p ../backups
    if [ ! -f ../backups/d-domain-original.caddy ]; then
        cp /etc/caddy/acli.d/sites/d.58nft.net.caddy ../backups/d-domain-original.caddy
    fi
fi
sudo bash -c 'source "$1"; acli_caddy_site_put "$2" "$3"' _ "$manager" "$owner" "$PWD/model-domain.pending.caddy"
mv model-domain.pending.caddy model-domain.caddy
printf '%s\n' "$owner" > model-domain.owner
echo "HTTPS site applied: https://$domain; Caddy obtains and renews its certificate."
