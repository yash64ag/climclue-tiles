#!/usr/bin/env bash
# Add ClimaClue to a server whose Caddy already serves other sites (e.g. trick.games). Run as root:
#   curl -fsSL https://raw.githubusercontent.com/yash64ag/climclue-tiles/main/server/setup-shared.sh | bash
# Changes: clones the public deploy repo to /srv/climaclue, adds /etc/caddy/sites/climaclue.caddy and one
# "import" line to /etc/caddy/Caddyfile (backup kept; validated before reload; restored if invalid),
# and a 2-minute update timer. Does NOT touch the firewall, Docker or any other site.
set -euo pipefail
main() {
  local CF=/etc/caddy/Caddyfile BK=/etc/caddy/Caddyfile.before-climaclue
  command -v caddy >/dev/null && systemctl is-active --quiet caddy || { echo "Caddy is not running here; use setup.sh instead"; exit 1; }
  echo "== caddy $(caddy version | cut -d' ' -f1)"
  command -v git >/dev/null || { apt-get update -qq; apt-get install -y -qq git >/dev/null; }

  echo "== downloading site and map data (about 1.2 GB)"
  mkdir -p /srv/climaclue
  if [ -d /srv/climaclue/public/.git ]; then git -C /srv/climaclue/public fetch -q --depth 1 origin main && git -C /srv/climaclue/public reset -q --hard origin/main; else git clone -q --depth 1 https://github.com/yash64ag/climclue-tiles /srv/climaclue/public; fi
  (cd /srv/climaclue/public/squares && sha256sum -c ../SHA256SUMS --quiet) && echo "map data verified"
  chmod -R a+rX /srv/climaclue

  echo "== adding ClimaClue to Caddy (other sites untouched)"
  local before; before=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1/ || true)
  mkdir -p /etc/caddy/sites
  install -m 644 /srv/climaclue/public/server/climaclue-shared.caddy /etc/caddy/sites/climaclue.caddy
  [ -f "$BK" ] || cp -p "$CF" "$BK"
  grep -qxF "import /etc/caddy/sites/*.caddy" "$CF" || printf "\n# Added for ClimaClue: loads /etc/caddy/sites/*.caddy (keep this line)\nimport /etc/caddy/sites/*.caddy\n" >> "$CF"
  if ! caddy validate --config "$CF" --adapter caddyfile >/tmp/climaclue-validate.log 2>&1; then
    cp -p "$BK" "$CF"; rm -f /etc/caddy/sites/climaclue.caddy
    echo "Caddy rejected the change; original restored, nothing else changed. Details:"; tail -5 /tmp/climaclue-validate.log; exit 1
  fi
  systemctl reload caddy

  echo "== automatic updates every 2 minutes"
  install -m 755 /srv/climaclue/public/server/update-shared.sh /usr/local/bin/climaclue-update
  install -m 644 /srv/climaclue/public/server/climaclue-update.service /srv/climaclue/public/server/climaclue-update.timer /etc/systemd/system/
  systemctl daemon-reload
  systemctl enable --now climaclue-update.timer >/dev/null

  echo "== checks"
  sleep 2
  echo "existing site before: $before  after: $(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1/)"
  echo "climaclue.com: $(curl -s -H "Host: climaclue.com" http://127.0.0.1/ | grep -o "<title>[^<]*" | head -1)"
  echo "port 443: $(curl -sk -o /dev/null -w "%{http_code}" --resolve climaclue.com:443:127.0.0.1 https://climaclue.com/)"
  : "$(curl -s -o /dev/null -w '%{http_code}' -H 'Host: climaclue.com' http://127.0.0.1/)"
  echo "map tile: $(curl -s -o /dev/null -w '%{http_code}' -H 'Host: climaclue.com' http://127.0.0.1/squares/t0_35.bin)  ocean tile: $(curl -s -o /dev/null -w '%{http_code}' -H 'Host: climaclue.com' http://127.0.0.1/squares/t0_0.bin)"
  echo "DONE"
}
main "$@"
