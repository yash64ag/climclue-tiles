#!/usr/bin/env bash
# READ-ONLY server check: changes nothing. Prints what serves the web ports, containers, firewall and
# front-door config names so ClimaClue can join the existing setup. Prints no passwords or keys.
echo "== system"; . /etc/os-release 2>/dev/null; echo "$PRETTY_NAME"; uname -m; nproc; free -h | awk 'NR==2{print "memory "$2" used "$3}'; df -h / | awk 'NR==2{print "disk "$2" used "$3}'
echo "== listening ports"; ss -ltnp 2>/dev/null | awk 'NR>1{print $4, $6}' | sed 's/users:((//; s/,pid=[0-9]*,fd=[0-9]*//g; s/))//' | sort -u
echo "== web servers installed"; for c in nginx caddy apache2 httpd traefik cloudflared docker pm2 node; do command -v $c >/dev/null && echo "$c: $(command -v $c)"; done
echo "== services running"; systemctl list-units --type=service --state=running --no-legend 2>/dev/null | awk '{print $1}' | grep -vE '^(systemd|dbus|cron|ssh|getty|serial|polkit|rsyslog|unattended|networkd|user@|snapd|multipathd|qemu|udisks|ModemManager|packagekit|fwupd|irqbalance|chrony|thermald)' 
echo "== containers"; docker ps --format '{{.Names}}  {{.Image}}  {{.Ports}}' 2>/dev/null || echo "docker not running"
echo "== docker compose projects"; docker compose ls 2>/dev/null
echo "== nginx sites (names only)"; [ -d /etc/nginx ] && grep -rhoE '^\s*(server_name|listen|proxy_pass)\s+[^;]+' /etc/nginx/sites-enabled /etc/nginx/conf.d 2>/dev/null | sed 's/^\s*//' | sort -u
echo "== caddy sites (address lines only)"; [ -f /etc/caddy/Caddyfile ] && grep -hE '^[^#[:space:]].*\{' /etc/caddy/Caddyfile /etc/caddy/*/*.caddy 2>/dev/null
echo "== cloudflared tunnels"; systemctl is-active cloudflared 2>/dev/null; ls /etc/cloudflared 2>/dev/null
echo "== firewall"; ufw status 2>/dev/null | head -20; iptables -S INPUT 2>/dev/null | head -5
echo "== /srv and /opt"; ls /srv /opt 2>/dev/null
echo "== end of check (nothing was changed)"
