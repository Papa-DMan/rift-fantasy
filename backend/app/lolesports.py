"""Bridge to the lolesports models in ../db.py (player, round, team, ...).

The fantasy code only relies on Player.id, Player.tag, Player.position,
Player.team and Round.id; everything else about pro play lives in db.py.
"""
from collections.abc import Iterable
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from db import Player, PlayerRole, Round, Team  # noqa: F401  (re-exported)


def player_position(player: Player) -> Optional[str]:
    """Roster slot key for a pro player: "top", "jungle", "mid", "adc",
    "support" or "coach" (PlayerRole values match the slot keys one to one).
    None means "no known position": the player can only go on bench."""
    return player.position.value if player.position else None


def team_names(db: Session, players: Iterable[Player]) -> dict[int, str]:
    """Pro team id -> name for the given players, in one query."""
    ids = {p.team for p in players if p.team is not None}
    if not ids:
        return {}
    return dict(db.execute(select(Team.id, Team.name).where(Team.id.in_(ids))).all())
