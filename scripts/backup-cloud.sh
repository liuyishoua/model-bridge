#!/usr/bin/env bash
set -euo pipefail
project=$(cd "$(dirname "$0")/.." && pwd)
backup_dir="$project/backups"
mkdir -p "$backup_dir"
chmod 700 "$backup_dir"
cd "$project/deploy"
sudo docker compose --env-file cloud.env -f compose.yaml stop open-webui
trap 'sudo docker compose --env-file cloud.env -f compose.yaml start open-webui >/dev/null' EXIT
archive="$backup_dir/model-webui-$(date -u +%Y%m%dT%H%M%SZ).tar.gz"
sudo tar -czf "$archive" --exclude='data/cache' data cloud.env
sudo chown "$(id -u):$(id -g)" "$archive"
chmod 600 "$archive"
echo "Backup created: $archive"
