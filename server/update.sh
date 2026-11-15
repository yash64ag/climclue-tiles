#!/usr/bin/env bash
# Pull the public deploy repository (built site + tiles); publish when it changed. Run every 2 minutes.
set -euo pipefail
main() {
  local PUB=/srv/climaclue/public force="${1:-}"
  exec 9>/srv/climaclue/.update.lock; flock -n 9 || exit 0
  git -C "$PUB" fetch -q --depth 1 origin main
  if [ "$(git -C "$PUB" rev-parse HEAD)" = "$(git -C "$PUB" rev-parse origin/main)" ] && [ "$force" != --force ]; then exit 0; fi
  git -C "$PUB" reset -q --hard origin/main
  (cd "$PUB/squares" && sha256sum -c ../SHA256SUMS --quiet)
  install -m 644 "$PUB/server/climaclue.caddy" /etc/caddy/sites/climaclue.caddy
  systemctl reload caddy
  docker compose -f "$PUB/server/docker-compose.yml" -p climaclue up -d --remove-orphans
  docker compose -f "$PUB/server/docker-compose.yml" -p climaclue exec -T web nginx -s reload >/dev/null 2>&1 || true
  echo "$(date -Is) published $(git -C "$PUB" log -1 --format=%s)"
}
main "$@"
