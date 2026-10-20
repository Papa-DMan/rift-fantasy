"""Fantasy scoring: points per player per game, lineups per round, standings.

Points come from PlayerGameStats rows (filled by the scraper) times the
league's scoring_rules. Games are tied to rounds by start time, since Game and
Series don't carry a round: a game belongs to the last round that locked at or
before it started (with a little grace for early starts).

Only starters score. A team's lineup for a round is snapshotted into
lineup_slots the first time it's needed after the round locks, so trades made
later don't rewrite history. Rounds that locked before the league's draft
finished don't count for anyone.
"""
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from db import Game, Player, PlayerGameStats, PlayerRole, Round, Series
from models import (
    Draft, DraftStatus, FantasyTeam as Team, FantasyTeamPlayer as TeamPlayer, League, LineupSlot, Slot,
)
from services.roster import as_utc, utcnow

# Per-stat multipliers. Stats are the PlayerGameStats columns; the rest are
# bonuses. Zero-weight stats are listed so commissioners can turn them on.
DEFAULT_SCORING_RULES: dict[str, float] = {
    "kills": 3,
    "deaths": -1,
    "assists": 2,
    "cs": 0.02,              # 1 point per 50 CS
    "vision_score": 0.05,    # 1 point per 20 vision
    "first_blood": 2,
    "win": 3,                # player's pro team won the game
    "ten_kill_assists": 2,   # 10+ kills + assists in one game
    "coach_win": 10,         # coaches score only this, per game their team wins
    "damage": 0,
    "gold": 0,
    "cs_at_15": 0,
    "gold_at_15": 0,
    "objective_steal": 0,
}
STAT_KEYS = ("kills", "deaths", "assists", "cs", "vision_score", "first_blood", "damage",
             "gold", "cs_at_15", "gold_at_15", "objective_steal")

# A game that starts a little before its round's lock time still counts for
# that round (lock times are the scheduled start of the day's first series).
ROUND_GRACE = timedelta(hours=2)


def effective_rules(league: League) -> dict[str, float]:
    """Defaults overlaid with whatever the league has stored."""
    return {**DEFAULT_SCORING_RULES, **(league.scoring_rules or {})}


def validate_scoring_rules(v: dict[str, Any]) -> dict[str, float]:
    unknown = set(v) - DEFAULT_SCORING_RULES.keys()
    if unknown:
        raise ValueError(f"unknown scoring rules: {sorted(unknown)}")
    out = {}
    for k, n in v.items():
        if isinstance(n, bool) or not isinstance(n, (int, float)) or not -100 <= n <= 100:
            raise ValueError(f"{k} must be a number between -100 and 100")
        out[k] = n
    return out


def score_stats(stats: PlayerGameStats, won: bool, rules: dict[str, float]) -> tuple[float, dict[str, float]]:
    breakdown: dict[str, float] = {}
    for key in STAT_KEYS:
        value = getattr(stats, key) or 0
        pts = rules.get(key, 0) * float(value)
        if pts:
            breakdown[key] = round(pts, 2)
    if won and rules.get("win"):
        breakdown["win"] = rules["win"]
    if (stats.kills or 0) + (stats.assists or 0) >= 10 and rules.get("ten_kill_assists"):
        breakdown["ten_kill_assists"] = rules["ten_kill_assists"]
    return round(sum(breakdown.values()), 2), breakdown


# ---------------------------------------------------------------- rounds

def all_rounds(db: Session) -> list[Round]:
    return list(db.scalars(select(Round).order_by(Round.lock_at, Round.id)))


def round_for(rounds: list[Round], started_at: Optional[datetime]) -> Optional[Round]:
    if started_at is None:
        return None
    started_at = as_utc(started_at)
    found = None
    for r in rounds:
        if as_utc(r.lock_at) <= started_at + ROUND_GRACE:
            found = r
    return found


def draft_completed_at(db: Session, league: League) -> Optional[datetime]:
    draft = db.scalar(select(Draft).where(Draft.league_id == league.id))
    if draft is None or draft.status != DraftStatus.COMPLETE:
        return None
    return as_utc(draft.completed_at)


def round_counts(rnd: Round, drafted_at: Optional[datetime]) -> bool:
    """A round counts if it locked after the league finished drafting."""
    return drafted_at is not None and as_utc(rnd.lock_at) >= drafted_at


def games_by_round(db: Session, rounds: list[Round]) -> dict[int, list[Game]]:
    """Round id -> the games that started in it (unstarted games are left out)."""
    out: dict[int, list[Game]] = defaultdict(list)
    for g in db.scalars(select(Game).where(Game.started_at.is_not(None))):
        r = round_for(rounds, g.started_at)
        if r is not None:
            out[r.id].append(g)
    return out


def round_status(rnd: Round, games: list[Game], drafted_at: Optional[datetime]) -> str:
    """upcoming, live, final, or before_draft."""
    now = utcnow()
    if now < as_utc(rnd.lock_at):
        return "upcoming"
    if not round_counts(rnd, drafted_at):
        return "before_draft"
    if now < as_utc(rnd.ends_at) or any(g.ended_at is None for g in games):
        return "live"
    return "final"


# ---------------------------------------------------------------- lineups

SLOT_ORDER = list(Slot)  # top, jungle, mid, adc, support, coach, bench

def auto_lineup(db: Session, league: League, team_id: int) -> list[tuple[Slot, int, int]]:
    """(slot, slot_index, player_id) for the team's current roster: each
    player starts at their position, earliest-acquired first, and the rest
    go to the bench. Mirrors roster_fits()."""
    rows = db.execute(
        select(TeamPlayer.player_id, Player.position)
        .join(Player, Player.id == TeamPlayer.player_id)
        .where(TeamPlayer.team_id == team_id)
        .order_by(TeamPlayer.acquired_at, TeamPlayer.id)
    ).all()
    slots = league.roster_slots or {}
    used: dict[str, int] = defaultdict(int)
    out: list[tuple[Slot, int, int]] = []
    bench = 0
    for player_id, position in rows:
        pos = position.value if position else None
        if pos and pos != "bench" and used[pos] < slots.get(pos, 0):
            out.append((Slot(pos), used[pos], player_id))
            used[pos] += 1
        else:
            out.append((Slot.BENCH, bench, player_id))
            bench += 1
    return out


def lineup_for(db: Session, league: League, team_id: int, rnd: Round, persist: bool = True) -> list[LineupSlot]:
    """The team's lineup for a round. Once a counted round has locked it's
    stored (snapshotted from the roster on first use); otherwise it's a
    preview of the current roster and nothing is written."""
    existing = list(db.scalars(
        select(LineupSlot).where(LineupSlot.team_id == team_id, LineupSlot.round_id == rnd.id)
    ))
    if existing:
        return existing
    preview = [LineupSlot(team_id=team_id, round_id=rnd.id, slot=s, slot_index=i, player_id=p)
               for s, i, p in auto_lineup(db, league, team_id)]
    if not persist or utcnow() < as_utc(rnd.lock_at) or not preview:
        return preview
    try:
        with db.begin_nested():
            db.add_all(preview)
    except IntegrityError:
        # Another request snapshotted it first; use theirs.
        preview = list(db.scalars(
            select(LineupSlot).where(LineupSlot.team_id == team_id, LineupSlot.round_id == rnd.id)
        ))
    db.commit()
    return preview


# ---------------------------------------------------------------- points

@dataclass
class GamePoints:
    game_id: int
    points: float
    breakdown: dict[str, float]


@dataclass
class PlayerRoundPoints:
    player_id: int
    points: float = 0.0
    games: list[GamePoints] = field(default_factory=list)


def player_round_points(db: Session, rules: dict[str, float], games: list[Game],
                        player_ids: list[int]) -> dict[int, PlayerRoundPoints]:
    """Points for each player across the given games."""
    out = {pid: PlayerRoundPoints(pid) for pid in player_ids}
    if not games or not player_ids:
        return out
    by_game = {g.id: g for g in games}
    players = {p.id: p for p in db.scalars(select(Player).where(Player.id.in_(player_ids)))}

    stats = db.scalars(select(PlayerGameStats).where(
        PlayerGameStats.game_id.in_(by_game), PlayerGameStats.player_id.in_(player_ids)))
    for s in stats:
        game, player = by_game[s.game_id], players[s.player_id]
        won = game.winner_id is not None and game.winner_id == player.team
        pts, breakdown = score_stats(s, won, rules)
        out[s.player_id].games.append(GamePoints(game.id, pts, breakdown))

    # Coaches don't have stat lines; they score when their team wins.
    coaches = [p for p in players.values() if p.position == PlayerRole.COACH]
    if coaches and rules.get("coach_win"):
        series = {s.id: s for s in db.scalars(
            select(Series).where(Series.id.in_({g.series for g in games})))}
        for coach in coaches:
            for g in games:
                s = series.get(g.series)
                if s is None or coach.team not in (s.team1, s.team2) or g.ended_at is None:
                    continue
                pts = rules["coach_win"] if g.winner_id == coach.team else 0
                out[coach.id].games.append(GamePoints(g.id, pts, {"coach_win": pts} if pts else {}))

    for p in out.values():
        p.games.sort(key=lambda gp: (by_game[gp.game_id].started_at, gp.game_id))
        p.points = round(sum(gp.points for gp in p.games), 2)
    return out


@dataclass
class SlotPoints:
    slot: LineupSlot
    points: float
    counts: bool        # bench players are shown but don't add to the total
    games: list[GamePoints]


def team_round(db: Session, league: League, team_id: int, rnd: Round, games: list[Game],
               rules: dict[str, float], persist: bool = True) -> tuple[float, list[SlotPoints]]:
    """A team's total for a round and its lineup with points. `games` are the
    round's games; pass [] and persist=False for rounds that don't count."""
    lineup = lineup_for(db, league, team_id, rnd, persist)
    lineup.sort(key=lambda s: (SLOT_ORDER.index(s.slot), s.slot_index))
    pts = player_round_points(db, rules, games, [s.player_id for s in lineup])
    slots = [SlotPoints(s, pts[s.player_id].points, s.slot != Slot.BENCH, pts[s.player_id].games)
             for s in lineup]
    total = round(sum(s.points for s in slots if s.counts), 2)
    return total, slots


def standings(db: Session, league: League) -> tuple[list[dict], list[dict]]:
    """(rounds, teams): every round with its status, and every team's points
    per counted round plus a season total, best first."""
    rules = effective_rules(league)
    rounds = all_rounds(db)
    drafted_at = draft_completed_at(db, league)
    teams = db.scalars(select(Team).where(Team.league_id == league.id).order_by(Team.id)).all()

    games = games_by_round(db, rounds)

    round_rows = []
    per_team: dict[int, dict[int, float]] = {t.id: {} for t in teams}
    for rnd in rounds:
        status = round_status(rnd, games[rnd.id], drafted_at)
        round_rows.append({"id": rnd.id, "name": rnd.name, "stage": rnd.stage.value,
                           "lock_at": rnd.lock_at, "ends_at": rnd.ends_at, "status": status})
        if status in ("live", "final"):
            for t in teams:
                per_team[t.id][rnd.id], _ = team_round(db, league, t.id, rnd, games[rnd.id], rules)

    team_rows = [{"team_id": t.id, "name": t.name,
                  "total": round(sum(per_team[t.id].values()), 2),
                  "rounds": per_team[t.id]} for t in teams]
    team_rows.sort(key=lambda r: (-r["total"], r["team_id"]))
    return round_rows, team_rows


def cache_points(db: Session, league: League) -> int:
    """Store each counted round's per-player points on lineup_slots.points.
    Run after new stats land (the scraper does). Returns rows updated."""
    rules = effective_rules(league)
    rounds = all_rounds(db)
    drafted_at = draft_completed_at(db, league)
    teams = db.scalars(select(Team.id).where(Team.league_id == league.id)).all()
    games = games_by_round(db, rounds)
    updated = 0
    for rnd in rounds:
        if round_status(rnd, games[rnd.id], drafted_at) not in ("live", "final"):
            continue
        for team_id in teams:
            _, slots = team_round(db, league, team_id, rnd, games[rnd.id], rules)
            for s in slots:
                if s.slot.id is not None and s.slot.points != s.points:
                    s.slot.points = s.points
                    updated += 1
    db.commit()
    return updated
