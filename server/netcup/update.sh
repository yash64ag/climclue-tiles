#!/usr/bin/env bash
# Run as root from a timer every few minutes: pull ClimaClue's prebuilt deploy branch and restart the API only when
# its code changed. Nothing is built on the server (no npm install, no compiler): the site, the climate tiles and the
# bundled API arrive ready-made from https://github.com/yash64ag/climclue-tiles (branch main).
# Caddy settings are NOT touched here: whoever manages the server's Caddy installs deploy file server/netcup/climaclue.caddy.
set -euo pipefail
PUB=/srv/climaclue/public
exec 9>/srv/climaclue/.update.lock; flock -n 9 || exit 0
as() { nice -n 10 runuser -u climaclue -- "$@"; }
as git -C "$PUB" fetch -q --depth 1 origin main
old=$(as git -C "$PUB" rev-parse HEAD); new=$(as git -C "$PUB" rev-parse origin/main)
[ "$old" = "$new" ] && [ "${1:-}" != --force ] && exit 0
api_before=$(sha256sum "$PUB/server/api/climaclue-api.mjs" 2>/dev/null || true)
as git -C "$PUB" reset -q --hard origin/main
(cd "$PUB/squares" && as sha256sum -c ../SHA256SUMS --quiet)
api_after=$(sha256sum "$PUB/server/api/climaclue-api.mjs")
if ! cmp -s "$PUB/server/netcup/climaclue-api.service" /etc/systemd/system/climaclue-api.service; then
  install -m 644 "$PUB/server/netcup/climaclue-api.service" /etc/systemd/system/climaclue-api.service
  systemctl daemon-reload; systemctl enable climaclue-api >/dev/null 2>&1 || true; api_before=changed
fi
[ "$api_before" = "$api_after" ] && [ "${1:-}" != --force ] || systemctl restart climaclue-api
# Shallow fetches leave old objects behind; tidy once in a while so the clone stays near 4 GB.
[ $((RANDOM % 50)) -eq 0 ] && as git -C "$PUB" gc -q --prune=now || true
echo "$(date -Is) published $(as git -C "$PUB" log -1 --format=%s)"
