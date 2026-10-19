# Rift Fantasy

Fantasy-football-style leagues for League of Legends esports, built for
friends playing along with Worlds. Create a league, invite friends with a
code, run a live snake draft, and trade players.

| Folder | What it is |
|---|---|
| [`backend/`](backend/README.md) | FastAPI + SQLAlchemy 2.0 API on PostgreSQL: lolesports data and scraping (`db.py`, `lolesports.py`), plus auth, leagues, drafts, rosters, trades (`app/`) |
| [`frontend/`](frontend/README.md) | Mobile-first React + Vite + TypeScript PWA that installs to a phone's home screen |

## Quick start

```bash
# API on :8000
cd backend
docker compose up -d db
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL=postgresql+psycopg://postgres:$POSTGRES_PASSWORD@localhost:5432/lolesports_fantasy
python -m app.create_tables --seed   # tables + Worlds teams, players, schedule
uvicorn app.main:app --reload

# App on :5173 (proxies /api to :8000)
cd frontend
npm install
npm run dev
```

Each folder's README covers configuration, tests, and deployment.

![Draft screen](frontend/screenshots/2-draft.png)

## License

LGPL-2.1, see [LICENSE](LICENSE).
