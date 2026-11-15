#!/usr/bin/env bash
# Every 2 minutes (climaclue-update.timer): keep ClimaClue loaded in the shared Caddy and publish changes
# from the public deploy repository. Other projects may rewrite /etc/caddy/Caddyfile when they deploy;
# if ClimaClue's one import line is gone, it is re-added (validated first; nothing changes if invalid).
set -euo pipefail
LINE='import /etc/caddy/sites/*.caddy'
CF=/etc/caddy/Caddyfile
PUB=/srv/climaclue/public

ensure_import() {
  grep -qxF "$LINE" "$CF" && return 0
  cp -p "$CF" /tmp/Caddyfile.climaclue-prev
  printf '\n# Added for ClimaClue: loads /etc/caddy/sites/*.caddy (keep this line)\n%s\n' "$LINE" >> "$CF"
  if caddy validate --config "$CF" --adapter caddyfile >/dev/null 2>&1; then
    systemctl reload caddy; echo "$(date -Is) re-added ClimaClue import line to $CF"
  else
    cp -p /tmp/Caddyfile.climaclue-prev "$CF"; echo "$(date -Is) could not re-add import line (Caddy rejected it); left $CF unchanged"
  fi
}

main() {
  local force="${1:-}"
  exec 9>/srv/climaclue/.update.lock; flock -n 9 || exit 0
  ensure_import
  git -C "$PUB" fetch -q --depth 1 origin main
  if [ "$(git -C "$PUB" rev-parse HEAD)" = "$(git -C "$PUB" rev-parse origin/main)" ] && [ "$force" != --force ]; then exit 0; fi
  git -C "$PUB" reset -q --hard origin/main
  (cd "$PUB/squares" && sha256sum -c ../SHA256SUMS --quiet)
  chmod -R a+rX /srv/climaclue
  if ! cmp -s "$PUB/server/climaclue-shared.caddy" /etc/caddy/sites/climaclue.caddy; then
    cp -p /etc/caddy/sites/climaclue.caddy /tmp/climaclue.caddy.prev
    install -m 644 "$PUB/server/climaclue-shared.caddy" /etc/caddy/sites/climaclue.caddy
    if caddy validate --config "$CF" --adapter caddyfile >/dev/null 2>&1; then systemctl reload caddy
    else install -m 644 /tmp/climaclue.caddy.prev /etc/caddy/sites/climaclue.caddy; echo "new ClimaClue Caddy settings invalid; kept the old ones"; fi
  fi
  # Keep this updater itself current (takes effect on the next run).
  cmp -s "$PUB/server/update-shared.sh" /usr/local/bin/climaclue-update || install -m 755 "$PUB/server/update-shared.sh" /usr/local/bin/climaclue-update
  echo "$(date -Is) published $(git -C "$PUB" log -1 --format=%s)"
}
main "$@"
