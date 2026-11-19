# ClimaClue on the Netcup server (shared with trick.games)

Prepared 19 Nov 2026 for the move from the old Hetzner server. Nothing here has been deployed.

## What ClimaClue is, as a service

- **Static site** (Vite build + ~31,000 SEO pages) in `site/`, and **climate data files** (tiles and map colours, 2.4 GB) in
  `squares/`. Caddy serves both straight from disk.
- **One small Node process** (`server/api/climaclue-api.mjs`, a single bundled file, no `npm install`): the chat,
  Google sign-in, saved places, membership (Stripe) and the question allowance. It listens on `127.0.0.1:$PORT`
  (here **3100**) and Caddy proxies `/api/*` to it. Needs Node 20 or newer; the server's Node 22 is right.
- **No database server.** State is a folder of JSON files (`STATE_DIRECTORY`).
- **Nothing is built on the server.** The ready-made site, data and API come from the public deploy repo
  `https://github.com/yash64ag/climclue-tiles`, branch `main`. (The app's source repo `yash64ag/Climate-Map` is not
  needed on the server; its `main` is far behind and must not be built. The climate data cannot be rebuilt on a server.)

## Layout on this server

    /srv/climaclue/public    clone of climclue-tiles (owner: climaclue)   ~4 GB; allow 10 GB
    /srv/climaclue/state     accounts, memberships, stored answers       copied from the old server; owner climaclue, mode 700
    /etc/climaclue/api.env   secrets, root-only (mode 600)               copied by hand from the old server

## Files in this folder

- `climaclue-api.service`: the API unit (user `climaclue`, port 3100, low CPU/IO weight so trick.games goes first).
- `climaclue.caddy`: the site block for Caddy (static files, `/api/*` to 3100). Same scheme as the old server:
  Cloudflare proxies the domain and ends public HTTPS; Caddy answers on port 80 and on 443 with an internal
  certificate, so no public certificate has to be issued at cutover. (Cloudflare's SSL mode stays as it is today.)
- `update.sh`: timer job (root): pulls `main`, checks the data checksums, restarts the API only when its code changed.

## What must be copied from the old server (never through Git)

1. `/var/lib/private/climaclue-api/` (the whole folder) to `/srv/climaclue/state/`: `accounts/` (users, sessions,
   saved places, memberships, question allowances, Stripe event ids), `answers.jsonl` (stored chat answers),
   `spend.json` (this month's chat spending).
2. `/etc/climaclue/api.env` to the same path. Variable names in it: `ANTHROPIC_API_KEY`, `STRIPE_SECRET_KEY`,
   `STRIPE_WEBHOOK_SECRET`, `CLIMACLUE_MONTHLY_CAP_USD`, and possibly `CLIMACLUE_BILLING_TESTERS`.

Copy the state last, with the old API stopped, right before DNS is switched: anything written on the old server
after the copy (a new member, a saved place) would be lost.

## Nothing changes outside the server

The domain stays `climaclue.com` (and `www`), so Stripe's webhook address (`https://climaclue.com/api/stripe/webhook`),
Google sign-in and everyone's sign-in cookies keep working. DNS is at Cloudflare: only the A records' IP changes.

## Admin commands here

    sudo -u climaclue STATE_DIRECTORY=/srv/climaclue/state node /srv/climaclue/public/server/api/climaclue-api.mjs --list-users

## Check after the move

- `curl -s http://127.0.0.1:3100/api/config` on the server: JSON with `"billingOpen":true,"packOffered":true`.
- `https://climaclue.com/`: the globe loads and is coloured; `https://climaclue.com/api/config` gives the same JSON.
- Sign in: saved places and membership are still there. Ask the chat one suggested question: an answer comes back.
