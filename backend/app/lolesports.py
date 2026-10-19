"""Stand-ins for the `player` and `round` tables that come from the
lolesports side of the app.

REPLACE THESE with imports of your real models. The fantasy code only relies on:
  * Player.id, Player.name, and a position (see `player_position` below)
  * Round.id
If your real models use a different declarative Base, make sure both share
one MetaData (or import the fantasy models onto your Base) so the foreign
keys to `player.id` / `round.id` resolve.
"""
from typing import Optional

from sqlalchemy import Identity, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models import BigIntPK


class Player(Base):
    __tablename__ = "player"

    id: Mapped[int] = mapped_column(BigIntPK, Identity(), primary_key=True)
    name: Mapped[str] = mapped_column(String(64))
    # top / jungle / mid / adc / support / coach
    role: Mapped[Optional[str]] = mapped_column(String(16))
    team_code: Mapped[Optional[str]] = mapped_column(String(16))  # e.g. "T1"


class Round(Base):
    __tablename__ = "round"

    id: Mapped[int] = mapped_column(BigIntPK, Identity(), primary_key=True)
    name: Mapped[str] = mapped_column(String(64))


def player_position(player: Player) -> Optional[str]:
    """Map a lolesports player to a roster slot key ("top", "mid", ... "coach").

    The draft and trade roster checks call this, so if your player table
    stores roles differently (e.g. "bottom" instead of "adc"), adapt it here.
    Returning None means "no known position": the player can only go on bench.
    """
    if not player.role:
        return None
    role = player.role.lower()
    return {"bottom": "adc", "bot": "adc", "jng": "jungle", "sup": "support",
            "utility": "support", "middle": "mid"}.get(role, role)
