# Rift Fantasy (frontend)

Mobile-first React + Vite + TypeScript app for the LoL Fantasy API in `../backend`.
It's a PWA: friends open the site on their phone and add it to the home screen,
and it launches full screen like a downloaded app.

## Run it locally

```bash
# backend (see ../backend/README.md), on :8000
cd ../backend && uvicorn app.main:app --reload

# frontend, on :5173
cd ../frontend
npm install
npm run dev            # open http://localhost:5173 (or your LAN IP from a phone)
```

The dev server proxies `/api/*` to `http://localhost:8000`, so the browser
only ever talks to one origin and the backend needs no CORS setup. Point the
proxy elsewhere with `API_PROXY_TARGET=http://host:port npm run dev`.

The draft pool is the real Worlds field. Seed it with
`python -m app.create_tables --seed` in `../backend`.

## Build and deploy

```bash
npm run build          # static files in dist/ (includes sw.js + manifest)
npm run preview        # serve dist/ on :4173 with the same /api proxy
```

Serve `dist/` from any static host and send `/api/*` to the backend with the
prefix stripped. Example nginx:

```nginx
location /api/ { proxy_pass http://127.0.0.1:8000/; }
location /     { root /srv/rift/dist; try_files $uri /index.html; }
```

If the API lives on a different domain instead, build with
`VITE_API_URL=https://api.example.com npm run build`; the backend then needs
FastAPI's `CORSMiddleware` allowing the site's origin.

**Home-screen install needs HTTPS** (localhost is exempt). On Android/Chrome
the app shows an Install button; on iPhone it shows "Share → Add to Home
Screen" since Safari has no install API.

## What's in it

| Screen | Backend calls |
|---|---|
| Sign in / create account | `POST /auth/register`, `POST /auth/login`, `GET /users/me` |
| Home: your leagues, create, join (`/join?code=XXXX` links prefill the code) | `GET /leagues`, `POST /leagues`, `POST /leagues/join` |
| League: status, invite code with native share, teams, rules, commissioner settings, leave | `GET/PATCH /leagues/{id}`, `POST .../invite-code`, `POST .../leave` |
| Draft: commissioner sets snake/linear, pick timer, time, order, then starts. Live room has the clock, player pool with position filters and search, the board, and your team | `GET/PATCH /leagues/{id}/draft`, `POST .../start`, `POST .../pick`, `GET .../players` |
| Rosters: any team's roster laid out by slot | `GET .../teams/{team_id}/roster` |
| Trades: inbox, sent, league history; propose with roster-fit check; accept, decline, withdraw | `/leagues/{id}/trades*` |

Notes:
- The draft room polls every 3s while live (polling also triggers the backend's
  autopick for expired clocks) and pauses when the app is in the background.
  Phones buzz when it becomes your pick (Android).
- The service worker precaches the app shell only; API calls always hit the network.
- Token lives in `localStorage`; a 401 signs you out.
- Scoring and lineups aren't in the UI yet because the backend doesn't have them.
- Icons are generated PNGs in `public/icons/`; swap them for real art any time.
