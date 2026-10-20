"""Background job that pulls Worlds data from the lolesports APIs into db.py's
tables, then refreshes fantasy points.

    python scraper.py            # loop forever (docker compose `scraper` service)
    python scraper.py --once     # one pass, then exit

Every pass is idempotent: series and games are upserted by their lolesports
ids, stats by (player, game), and finished games are skipped once their stats
are stored. A pass:

1. getSchedule for the tracked leagues -> `series` (teams, stage)
2. getEventDetails per match -> `game` rows
3. for each started game that isn't final yet, the livestats feed ->
   started_at / ended_at / winner_id and `player_game_stats`
4. fantasy points for every drafted league (lineup snapshots + cached points)

The livestats feed has no total damage, vision score or objective steals:
damage and objective_steal are stored as 0, and vision_score is wards placed
plus wards destroyed. The feed doesn't name a game's winner either; it's the
side with more inhibitors, then towers, then gold in the final frame (the
series result overrides it for the deciding game).
"""
import argparse
import logging
import os
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import requests
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from db import Game, Player, PlayerGameStats, PlayerRole, Series, SeriesStage, Team
from models import League, LeagueStatus
from services.scoring import cache_points

log = logging.getLogger("scraper")

WORLDS_LEAGUE_ID = "98767975604431411"
API_KEY = "0TvQnueqKa5mxJntVWt0w4LpLfEkrV1Ta8rQBb9Z"  # the public key lolesports.com itself uses
ESPORTS_API = "https://esports-api.lolesports.com/persisted/gw"
FEED_API = "https://feed.lolesports.com/livestats/v1"

LEAGUE_IDS = os.getenv("SCRAPER_LEAGUE_IDS", WORLDS_LEAGUE_ID).split(",")
# Older events in the schedule (previous years' Worlds) are ignored.
SINCE = datetime.fromisoformat(os.getenv("SCRAPER_SINCE", "2026-01-01T00:00:00+00:00"))
LIVE_INTERVAL = int(os.getenv("SCRAPER_LIVE_INTERVAL", "60"))      # seconds, while a match is on
IDLE_INTERVAL = int(os.getenv("SCRAPER_IDLE_INTERVAL", "900"))     # seconds, otherwise

ROLE_MAP = {"top": PlayerRole.TOP, "jungle": PlayerRole.JUNGLE, "mid": PlayerRole.MID,
            "bottom": PlayerRole.ADC, "support": PlayerRole.SUPPORT}
STEP = timedelta(minutes=5)       # coarse probe step through a game's timeline
MAX_GAME = timedelta(hours=2)     # nothing runs longer than this


# ---------------------------------------------------------------- HTTP

class LolEsportsApi:
    """Thin client. Every call returns parsed JSON, or None when there is no
    data (204, 404, empty body). Network and 5xx errors raise, so a failed
    pass stops early instead of writing half-read data."""

    def __init__(self, session: Optional[requests.Session] = None):
        self.http = session or requests.Session()
        self.http.headers["x-api-key"] = API_KEY

    def _get(self, url: str, params: dict) -> Optional[dict]:
        r = self.http.get(url, params={k: v for k, v in params.items() if v is not None}, timeout=15)
        if r.status_code in (204, 404) or not r.content:
            return None
        r.raise_for_status()
        return r.json()

    def schedule(self, league_ids: list[str]) -> list[dict]:
        """Every event for the leagues, walking the pages in both directions
        (the first page is "around now")."""
        events: dict[str, dict] = {}
        for direction in ("older", "newer"):
            token = None
            while True:
                data = self._get(f"{ESPORTS_API}/getSchedule",
                                 {"hl": "en-US", "leagueId": ",".join(league_ids), "pageToken": token})
                sched = (data or {}).get("data", {}).get("schedule") or {}
                for e in sched.get("events", []):
                    key = (e.get("match") or {}).get("id") or e.get("startTime")
                    events[key] = e
                token = (sched.get("pages") or {}).get(direction)
                if not token:
                    break
        return list(events.values())

    def event_details(self, match_id: str) -> Optional[dict]:
        data = self._get(f"{ESPORTS_API}/getEventDetails", {"hl": "en-US", "id": match_id})
        return (data or {}).get("data", {}).get("event")

    def window(self, game_id: str, at: Optional[datetime] = None) -> Optional[dict]:
        return self._get(f"{FEED_API}/window/{game_id}", {"startingTime": api_time(at) if at else None})

    def details(self, game_id: str, at: Optional[datetime] = None) -> Optional[dict]:
        return self._get(f"{FEED_API}/details/{game_id}", {"startingTime": api_time(at) if at else None})


def api_time(dt: datetime) -> str:
    """The feed wants UTC on a 10-second boundary."""
    dt = dt.astimezone(timezone.utc).replace(microsecond=0)
    dt -= timedelta(seconds=dt.second % 10)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------- matching

def norm(s: Optional[str]) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def next_id(db: Session, model) -> int:
    """db.py's tables use plain BIGINT keys and the seed writes explicit ids,
    so new rows take max(id) + 1 rather than trusting a sequence. Only this
    job inserts into these tables."""
    return (db.scalar(select(func.max(model.id))) or 0) + 1


def find_team(db: Session, api_team: dict) -> Optional[int]:
    """Our team id for a lolesports team, by name ("Dplus KIA" ~ "Dplus Kia",
    "Invictus Gaming" ~ "Shanghai Invictus Gaming Meituan") or code."""
    name, code = norm(api_team.get("name")), norm(api_team.get("code"))
    if not name or name == "tbd":
        return None
    teams = db.execute(select(Team.id, Team.name)).all()
    for tid, tname in teams:
        if norm(tname) in (name, code):
            return tid
    for tid, tname in teams:
        n = norm(tname)
        if len(name) >= 3 and (name in n or n in name):
            return tid
    log.warning("no team matches %r (%s)", api_team.get("name"), api_team.get("code"))
    return None


def series_stage(block_name: Optional[str]) -> SeriesStage:
    b = (block_name or "").lower()
    if "swiss" in b:
        return SeriesStage.SWISS
    if "final" in b or "knockout" in b or "bracket" in b:
        return SeriesStage.KNOCKOUT
    return SeriesStage.PLAY_IN


def match_players(db: Session, metadata: dict, team_ids: dict[str, Optional[int]]) -> dict[int, int]:
    """participantId (1-10) -> our player id. Feed names are "<TEAM> <tag>",
    so a player matches when the feed name ends with their tag; the longest
    tag wins, so "G2 Hans Sama" doesn't pick a player tagged "Sama"."""
    out: dict[int, int] = {}
    for side in ("blueTeamMetadata", "redTeamMetadata"):
        team_meta = metadata.get(side) or {}
        team_id = team_ids.get(team_meta.get("esportsTeamId"))
        q = select(Player).where(Player.position != PlayerRole.COACH)
        candidates = db.scalars(q.where(Player.team == team_id) if team_id else q).all()
        for p in team_meta.get("participantMetadata", []):
            feed_name = norm(p.get("summonerName"))
            role = ROLE_MAP.get(p.get("role"))
            hits = [c for c in candidates if norm(c.tag) and feed_name.endswith(norm(c.tag))]
            hits.sort(key=lambda c: (c.position == role, len(c.tag)), reverse=True)
            if hits:
                out[p["participantId"]] = hits[0].id
            else:
                log.warning("no player matches %r", p.get("summonerName"))
    return out


# ---------------------------------------------------------------- feed timeline

class Timeline:
    """Reads one game's window feed at chosen times, caching each probe."""

    def __init__(self, api: LolEsportsApi, game_id: str):
        self.api, self.game_id = api, game_id
        self.cache: dict[str, list[dict]] = {}
        self.metadata: Optional[dict] = None

    def frames(self, at: Optional[datetime]) -> list[dict]:
        key = api_time(at) if at else "latest"
        if key not in self.cache:
            data = self.api.window(self.game_id, at) or {}
            self.metadata = self.metadata or data.get("gameMetadata")
            frames = sorted(data.get("frames") or [], key=lambda f: f["rfc460Timestamp"])
            self.cache[key] = frames
        return self.cache[key]

    def in_game(self, at: datetime) -> bool:
        return any(f.get("gameState") == "in_game" for f in self.frames(at))

    def finished(self, at: datetime) -> bool:
        return any(f.get("gameState") == "finished" for f in self.frames(at))

    def bisect(self, lo: datetime, hi: datetime, pred) -> datetime:
        """Earliest time in (lo, hi] where pred holds, to 10s; pred(lo) is
        false and pred(hi) true."""
        while hi - lo > timedelta(seconds=10):
            mid = lo + (hi - lo) / 2
            if pred(mid):
                hi = mid
            else:
                lo = mid
        return hi


def read_game(api: LolEsportsApi, game_id: str) -> Optional[dict]:
    """Start, end (None while live) and final frame for one game, or None if
    the feed has nothing yet. Before a game the feed is empty; from the first
    frame on it's in_game until a finished frame (or nothing) after the end."""
    tl = Timeline(api, game_id)
    first = tl.frames(None)
    if not first:
        return None
    anchor = parse_ts(first[0]["rfc460Timestamp"])

    # Start: step back until the feed is empty, then narrow it down.
    t = anchor
    while anchor - t < MAX_GAME and tl.frames(t - STEP):
        t -= STEP
    if anchor - t < MAX_GAME:
        t = tl.bisect(t - STEP, t, lambda at: bool(tl.frames(at)))
    start = parse_ts(tl.frames(t)[0]["rfc460Timestamp"])

    # End: step forward while still in game, then narrow it down.
    now = utcnow()
    t = start
    while t - start < MAX_GAME and t + STEP < now and tl.in_game(t + STEP):
        t += STEP
    if t + STEP >= now and tl.in_game(t):
        live = tl.frames(now - timedelta(seconds=60)) or tl.frames(t)
        return {"tl": tl, "start": start, "end": None, "final": live[-1] if live else None}
    end = tl.bisect(t, t + STEP, lambda at: not tl.in_game(at))

    finished = [f for f in tl.frames(end) if f.get("gameState") == "finished"]
    before = tl.frames(end - timedelta(seconds=10))
    final = finished[0] if finished else (before[-1] if before else None)
    return {"tl": tl, "start": start, "end": parse_ts(final["rfc460Timestamp"]) if final else end,
            "final": final}


def participants(frame: dict) -> dict[int, dict]:
    out = {}
    for side in ("blueTeam", "redTeam"):
        for p in (frame.get(side) or {}).get("participants", []):
            out[p["participantId"]] = p
    return out


def first_blood(tl: Timeline, start: datetime, end: datetime) -> Optional[int]:
    """participantId who drew first blood: bisect to the first frame with a
    kill on the board, then whoever has one."""
    def total_kills(at: datetime) -> int:
        frames = tl.frames(at)
        return sum(p["kills"] for p in participants(frames[-1]).values()) if frames else 0
    if total_kills(end) == 0:
        return None
    at = tl.bisect(start, end, lambda t: total_kills(t) > 0)
    for f in tl.frames(at):
        killers = [pid for pid, p in participants(f).items() if p["kills"] > 0]
        if killers:
            return killers[0]
    return None


def winner_side(final: dict) -> str:
    def strength(side: str) -> tuple:
        t = final.get(side) or {}
        return (t.get("inhibitors", 0), t.get("towers", 0), t.get("totalGold", 0))
    return "blue" if strength("blueTeam") >= strength("redTeam") else "red"


# ---------------------------------------------------------------- sync

def sync_series(db: Session, event: dict) -> Optional[Series]:
    match = event.get("match") or {}
    if event.get("type") != "match" or not match.get("id"):
        return None
    series = db.scalar(select(Series).where(Series.external_id == match["id"]))
    if series is None:
        series = Series(id=next_id(db, Series), external_id=match["id"])
        db.add(series)
    teams = match.get("teams") or []
    series.stage = series_stage(event.get("blockName"))
    if len(teams) == 2:
        series.team1 = find_team(db, teams[0]) or series.team1
        series.team2 = find_team(db, teams[1]) or series.team2
    db.flush()
    return series


def sync_games(db: Session, api: LolEsportsApi, series: Series) -> tuple[list[tuple[Game, dict]], list[dict]]:
    """Upsert the series' games. Returns (game, api game) pairs and the
    match's teams from getEventDetails (which, unlike the schedule, carry ids)."""
    event = api.event_details(series.external_id)
    out = []
    for g in ((event or {}).get("match") or {}).get("games", []):
        if g.get("state") == "unneeded":
            continue
        game = db.scalar(select(Game).where(Game.external_id == g["id"]))
        if game is None:
            game = Game(id=next_id(db, Game), external_id=g["id"], number=g["number"], series=series.id)
            db.add(game)
            db.flush()
        out.append((game, g))
    return out, ((event or {}).get("match") or {}).get("teams") or []


def game_is_final(db: Session, game: Game) -> bool:
    return game.ended_at is not None and db.scalar(
        select(func.count()).select_from(PlayerGameStats).where(PlayerGameStats.game_id == game.id)) > 0


def sync_game_stats(db: Session, api: LolEsportsApi, game: Game, team_ids: dict[str, Optional[int]], series_winner: Optional[int],
                    deciding: bool) -> bool:
    """Read the feed for one game and store its stats. Returns True if the
    game is live (so the next pass should come soon)."""
    info = read_game(api, game.external_id)
    if info is None or info["final"] is None:
        return False
    tl, start, end, final = info["tl"], info["start"], info["end"], info["final"]
    meta = tl.metadata or {}
    for side in ("blueTeamMetadata", "redTeamMetadata"):
        ext = (meta.get(side) or {}).get("esportsTeamId")
        if ext and ext not in team_ids:
            team_ids[ext] = None
    players = match_players(db, meta, team_ids)

    game.started_at = start
    end_at = end or parse_ts(final["rfc460Timestamp"])
    at_15 = min(start + timedelta(minutes=15), end_at)
    frames_15 = tl.frames(at_15)
    stats_15 = participants(frames_15[0]) if frames_15 else {}
    fb = first_blood(tl, start, end_at)
    detail = (api.details(game.external_id, end_at) or {}).get("frames") or []
    wards = {p["participantId"]: p.get("wardsPlaced", 0) + p.get("wardsDestroyed", 0)
             for p in (detail[-1]["participants"] if detail else [])}

    for pid, p in participants(final).items():
        player_id = players.get(pid)
        if player_id is None:
            continue
        row = db.scalar(select(PlayerGameStats).where(
            PlayerGameStats.player_id == player_id, PlayerGameStats.game_id == game.id))
        if row is None:
            row = PlayerGameStats(id=next_id(db, PlayerGameStats), player_id=player_id, game_id=game.id)
            db.add(row)
        early = stats_15.get(pid, {})
        row.kills, row.deaths, row.assists = p["kills"], p["deaths"], p["assists"]
        row.cs, row.gold = p["creepScore"], p["totalGold"]
        row.cs_at_15, row.gold_at_15 = early.get("creepScore", 0), early.get("totalGold", 0)
        row.first_blood = pid == fb
        row.vision_score = wards.get(pid, 0)
        row.damage, row.objective_steal = 0, 0
        db.flush()

    if end is not None:
        game.ended_at = end
        side = winner_side(final)
        team_ext = (meta.get(f"{side}TeamMetadata") or {}).get("esportsTeamId")
        game.winner_id = team_ids.get(team_ext)
        if deciding and series_winner is not None:
            game.winner_id = series_winner
    db.commit()
    return end is None


def run_once(db: Session, api: LolEsportsApi) -> bool:
    """One full pass. Returns True if anything is live right now."""
    live = False
    for event in api.schedule(LEAGUE_IDS):
        if parse_ts(event["startTime"]) < SINCE:
            continue
        series = sync_series(db, event)
        db.commit()
        if series is None or event.get("state") == "unstarted":
            continue
        live |= event.get("state") == "inProgress"
        games, api_teams = sync_games(db, api, series)
        team_ids = {t["id"]: find_team(db, t) for t in api_teams if t.get("id")}
        series_teams = [t for t in (event.get("match") or {}).get("teams") or []]
        winners = [find_team(db, t) for t in series_teams if (t.get("result") or {}).get("outcome") == "win"]
        played = [(g, ag) for g, ag in games if ag.get("state") in ("completed", "inProgress")]
        for i, (game, _) in enumerate(played):
            if game_is_final(db, game):
                continue
            # The deciding game of a finished series is won by the series winner.
            deciding = event.get("state") == "completed" and i == len(played) - 1
            try:
                live |= sync_game_stats(db, api, game, team_ids, winners[0] if winners else None, deciding)
            except requests.RequestException:
                db.rollback()
                log.exception("feed error for game %s; will retry next pass", game.external_id)
        db.commit()

    for league in db.scalars(select(League).where(
            League.status.in_([LeagueStatus.ACTIVE, LeagueStatus.FINISHED]))).all():
        cache_points(db, league)
    return live


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--once", action="store_true", help="one pass, then exit")
    args = parser.parse_args()
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(message)s")

    from db import DBManager
    from deps import dbc
    dbm = DBManager(conf=dbc)
    api = LolEsportsApi()
    while True:
        started = time.monotonic()
        live = False
        try:
            with dbm._sessionfactory() as db:
                live = run_once(db, api)
            log.info("pass done in %.0fs%s", time.monotonic() - started, " (live)" if live else "")
        except Exception:
            log.exception("pass failed; retrying later")
        if args.once:
            return
        time.sleep(LIVE_INTERVAL if live else IDLE_INTERVAL)


if __name__ == "__main__":
    main()
