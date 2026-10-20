"""Roster-shape rules shared by the draft and trades.

A team's players must fit the league's `roster_slots`: each player fills a
slot for their position first, and any overflow has to fit on the bench.
"""
from collections import Counter
from collections.abc import Iterable
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from lolesports import Player, player_position
from models import League, FantasyTeamPlayer as TeamPlayer


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """SQLite hands back naive datetimes; treat them as UTC."""
    if dt is None or dt.tzinfo is not None:
        return dt
    return dt.replace(tzinfo=timezone.utc)


def roster_size(league: League) -> int:
    return sum(league.roster_slots.values())


def roster_fits(positions: Iterable[Optional[str]], slots: dict[str, int]) -> bool:
    counts = Counter(positions)
    overflow = 0
    for pos, n in counts.items():
        capacity = slots.get(pos, 0) if pos and pos != "bench" else 0
        overflow += max(0, n - capacity)
    return overflow <= slots.get("bench", 0)


def team_positions(db: Session, team_id: int) -> list[Optional[str]]:
    players = db.scalars(
        select(Player).join(TeamPlayer, TeamPlayer.player_id == Player.id)
        .where(TeamPlayer.team_id == team_id)
    )
    return [player_position(p) for p in players]
