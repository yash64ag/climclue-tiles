#!/usr/bin/env bash
# Pull the public deploy repository; publish when it changed. Run every 2 minutes by climaclue-update.timer.
set -euo pipefail
main() {
  local PUB=/srv/climaclue/public force="${1:-}"
  exec 9>/srv/climaclue/.update.lock; flock -n 9 || exit 0
  git -C "$PUB" fetch -q --depth 1 origin main
  if [ "$(git -C "$PUB" rev-parse HEAD)" = "$(git -C "$PUB" rev-parse origin/main)" ] && [ "$force" != --force ]; then exit 0; fi
  git -C "$PUB" reset -q --hard origin/main
  (cd "$PUB/squares" && sha256sum -c ../SHA256SUMS --quiet)
  chmod -R a+rX /srv/climaclue
  if ! cmp -s "$PUB/server/climaclue-shared.caddy" /etc/caddy/sites/climaclue.caddy; then
    cp -p /etc/caddy/sites/climaclue.caddy /etc/caddy/sites/climaclue.caddy.prev
    install -m 644 "$PUB/server/climaclue-shared.caddy" /etc/caddy/sites/climaclue.caddy
    if caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile >/dev/null 2>&1; then systemctl reload caddy
    else mv /etc/caddy/sites/climaclue.caddy.prev /etc/caddy/sites/climaclue.caddy; echo "new Caddy settings invalid; kept the old ones"; fi
  fi
  echo "$(date -Is) published $(git -C "$PUB" log -1 --format=%s)"
}
main "$@"
