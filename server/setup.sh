#!/usr/bin/env bash
# One-time setup on the shared Hetzner server (Ubuntu or Debian, as root):
#   curl -fsSL https://raw.githubusercontent.com/yash64ag/climclue-tiles/main/server/setup.sh | bash
# Installs Docker, Caddy (shared front door) and a Cloudflare-only firewall, then serves ClimaClue.
set -euo pipefail
main() {
  export DEBIAN_FRONTEND=noninteractive
  echo "== installing packages"
  apt-get update -qq
  apt-get install -y -qq git rsync curl ufw caddy >/dev/null
  command -v docker >/dev/null || apt-get install -y -qq docker.io >/dev/null
  docker compose version >/dev/null 2>&1 || apt-get install -y -qq docker-compose-v2 >/dev/null
  systemctl enable --now docker >/dev/null

  echo "== downloading site and map data (about 1.2 GB)"
  mkdir -p /srv/climaclue
  [ -d /srv/climaclue/public/.git ] || git clone -q --depth 1 https://github.com/yash64ag/climclue-tiles /srv/climaclue/public
  (cd /srv/climaclue/public/squares && sha256sum -c ../SHA256SUMS --quiet) && echo "map data verified"

  echo "== front door (Caddy)"
  mkdir -p /etc/caddy/sites
  install -m 644 /srv/climaclue/public/server/Caddyfile /etc/caddy/Caddyfile
  systemctl enable --now caddy >/dev/null

  echo "== automatic updates every 2 minutes"
  install -m 755 /srv/climaclue/public/server/update.sh /usr/local/bin/climaclue-update
  install -m 644 /srv/climaclue/public/server/climaclue-update.service /srv/climaclue/public/server/climaclue-update.timer /etc/systemd/system/
  systemctl daemon-reload
  /usr/local/bin/climaclue-update --force
  systemctl enable --now climaclue-update.timer >/dev/null

  echo "== firewall: SSH from anywhere, web only from Cloudflare"
  ufw allow OpenSSH >/dev/null
  for ip in $(curl -fsS https://www.cloudflare.com/ips-v4) $(curl -fsS https://www.cloudflare.com/ips-v6); do
    ufw allow proto tcp from "$ip" to any port 80,443 comment cloudflare >/dev/null
  done
  ufw --force enable >/dev/null

  echo "== checks"
  curl -fsS -o /dev/null -w 'container: %{http_code}\n' http://127.0.0.1:8081/
  curl -fsS -o /dev/null -w 'front door: %{http_code}\n' -H 'Host: climaclue.com' http://127.0.0.1/
  echo "DONE. Server IPv4: $(curl -fsS -4 https://ifconfig.co 2>/dev/null || hostname -I | cut -d' ' -f1)"
}
main "$@"
