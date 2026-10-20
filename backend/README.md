# LoL Fantasy API

FastAPI + SQLAlchemy 2.0 backend for friends-only League of Legends fantasy
leagues (Worlds first). Pro-play data (teams, players, rounds, games, stats,
live feed frames) lives in `db.py`, with the lolesports API client in
`lolesports.py` / `lolesportsapi.py`. The fantasy schema lives in
`app/models.py`. Scoring is deliberately left out until the rules are settled.

## Run it

PostgreSQL is the primary database; `docker compose up -d db` starts the one
in `docker-compose.yaml`.

```bash
pip install -r requirements.txt
export DATABASE_URL=postgresql+psycopg://postgres:$POSTGRES_PASSWORD@localhost:5432/lolesports_fantasy
python -m app.create_tables --seed       # all tables, plus db.seed(): Worlds rounds, teams,
                                         # players, and games from the lolesports API
JWT_SECRET=$(openssl rand -hex 32) uvicorn app.main:app --reload
# open http://localhost:8000/docs

pytest -q                                # in-memory SQLite, no setup needed
TEST_DATABASE_URL=postgresql+psycopg://user:pw@localhost:5432/fantasy_test pytest -q
                                         # same suite on a throwaway Postgres DB (tables are dropped!)
```

| Env var | Default | |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg://postgres@localhost:5432/lolesports_fantasy` | psycopg 3 driver; SQLite URLs also work for quick local runs |
| `JWT_SECRET` | dev placeholder | **set this** in any real deployment |
| `ACCESS_TOKEN_MINUTES` | `10080` (7 days) | |
| `DEFAULT_TOURNAMENT_ID` | `worlds-2026` | used when a league doesn't pass one |

## How the fantasy side uses the lolesports tables

`app/lolesports.py` is the bridge to `db.py`. The fantasy code only uses
`Player.id`, `Player.tag`, `Player.position`, `Player.team` and `Round.id`.
`PlayerRole` values (`top`, `jungle`, `mid`, `adc`, `support`, `coach`) are
the roster slot keys, so `player_position()` is a straight `.value`.

The API's player objects map the pro tables like this: `name` is the in-game
tag (`Faker`), `real_name` is `Player.name`, `role` is the position,
`team_code` is the pro team's name, and `region` is the region.

## Endpoints

Auth is a bearer token: `POST /auth/login` takes an OAuth2 form
(`username` = email, `password`), and every other call sends
`Authorization: Bearer <token>`. League routes 404 for non-members so private
leagues don't leak.

**Users**
- `POST /auth/register` `{email, password, display_name}`
- `POST /auth/login` (form) → `{access_token}`
- `GET /users/me`

**Leagues**
- `POST /leagues` `{name, team_name, max_teams?, roster_slots?, trade_deadline?, tournament_id?}`: creates the league, the creator's commissioner team, and a scheduled draft
- `GET /leagues`: my leagues
- `GET /leagues/{id}`: details and teams (invite code shown to the commissioner only)
- `PATCH /leagues/{id}`: commissioner; roster slots and team count lock once the draft starts
- `POST /leagues/join` `{invite_code, team_name}`: only while the league is in setup and not full
- `POST /leagues/{id}/invite-code`: commissioner; issues a new code and kills the old one
- `POST /leagues/{id}/leave`: before the draft, non-commissioners
- `GET /leagues/{id}/teams/{team_id}/roster`
- `GET /leagues/{id}/players?available=true&position=mid`

**Draft**
- `PATCH /leagues/{id}/draft` `{type: snake|linear, seconds_per_pick, scheduled_for}`: commissioner, before it starts
- `POST /leagues/{id}/draft/start` `{order?: [team_id, ...]}`: commissioner; random order if omitted. Creates every `DraftPick` row up front (rounds = total roster slots).
- `GET /leagues/{id}/draft`: the board, who's on the clock, and the pick deadline. Poll it during the draft.
- `POST /leagues/{id}/draft/pick` `{player_id}`

**Trades** (after the draft, before `trade_deadline`)
- `POST /leagues/{id}/trades` `{receiver_team_id, give_player_ids, receive_player_ids, message?}`
- `GET /leagues/{id}/trades?status_filter=proposed&mine=true`
- `GET /leagues/{id}/trades/{trade_id}`
- `POST .../{trade_id}/accept` (receiver), `/reject` (receiver), `/cancel` (proposer)

## Rules worth knowing

- **Roster fit.** Every player fills a slot for their position, and any overflow
  must fit on the bench. The draft and both sides of a trade enforce this, so
  uneven trades (2-for-1) only work when the receiving side has room.
- **Pick timer without a worker.** When a clock runs out, the next read or pick
  autopicks for that team (the first available player that fits; swap in
  rankings once you have them). Autopicks are stamped at their deadline, so
  later clocks stay on schedule.
- **Concurrency.** Draft rows and trades are locked `FOR UPDATE` on
  Postgres, and the `(league_id, player_id)` unique constraint on
  `team_players` is the backstop against double ownership.
- **Trades complete on accept.** Ownership is re-checked at accept time. Any
  other open offer involving a player who moved gets cancelled. `ACCEPTED` and
  `VETOED` are unused until you want a commissioner veto window.

## Changes from the db-design file

- **Postgres types.** Primary keys are `BIGINT GENERATED BY DEFAULT AS IDENTITY`,
  enums are native Postgres ENUM types, `scoring_rules` / `roster_slots` are
  `JSONB`, and timestamps are `timestamptz`.
- On SQLite (tests only) ids fall back to `INTEGER` and JSONB to JSON, because
  SQLite only auto-increments `INTEGER PRIMARY KEY`.
- The fantasy `Base` in `app/db.py` reuses `db.Base.metadata`, so foreign keys
  to `player.id` / `round.id` resolve and `create_all` builds both sides. It
  keeps its own registry because both sides have a class called `Team`
  (`team` = pro team, `teams` = fantasy team).
- `db.py` keys are plain `BIGINT` (BIGSERIAL on Postgres), which SQLite won't
  auto-increment, so the tests insert pro teams and players with explicit ids.

## Not done yet

Scoring and lineups (`LineupSlot` exists but has no endpoints), free-agent
pickups and waivers, commissioner veto, real-time draft updates (websockets),
refresh tokens and password reset, and Alembic migrations.
