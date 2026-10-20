from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from models import DraftStatus, DraftType, LeagueStatus, TradeStatus

ROSTER_SLOT_KEYS = {"top", "jungle", "mid", "adc", "support", "coach", "bench"}
DEFAULT_ROSTER_SLOTS = {"top": 1, "jungle": 1, "mid": 1, "adc": 1, "support": 1,
                        "coach": 1, "bench": 2}


def validate_roster_slots(v: dict[str, int]) -> dict[str, int]:
    unknown = set(v) - ROSTER_SLOT_KEYS
    if unknown:
        raise ValueError(f"unknown roster slots: {sorted(unknown)}")
    if any(n < 0 or n > 5 for n in v.values()):
        raise ValueError("each slot count must be between 0 and 5")
    if sum(v.values()) < 1:
        raise ValueError("roster needs at least one slot")
    return v


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------- auth / users

class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=1, max_length=64)


class UserOut(ORM):
    id: int
    email: str
    display_name: str
    created_at: Optional[datetime] = None


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---------------------------------------------------------------- leagues

class LeagueCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    team_name: str = Field(min_length=1, max_length=64, description="The creator's own team")
    tournament_id: Optional[str] = Field(None, max_length=64)
    max_teams: int = Field(8, ge=2, le=20)
    roster_slots: dict[str, int] = Field(default_factory=lambda: dict(DEFAULT_ROSTER_SLOTS))
    trade_deadline: Optional[datetime] = None

    @field_validator("roster_slots")
    @classmethod
    def _check_slots(cls, v: dict[str, int]) -> dict[str, int]:
        return validate_roster_slots(v)


class LeagueUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    max_teams: Optional[int] = Field(None, ge=2, le=20)
    roster_slots: Optional[dict[str, int]] = None
    trade_deadline: Optional[datetime] = None

    @field_validator("roster_slots")
    @classmethod
    def _check_slots(cls, v: Optional[dict[str, int]]) -> Optional[dict[str, int]]:
        return v if v is None else validate_roster_slots(v)


class JoinLeague(BaseModel):
    invite_code: str = Field(min_length=1, max_length=16)
    team_name: str = Field(min_length=1, max_length=64)


class TeamOut(ORM):
    id: int
    name: str
    user_id: int
    is_commissioner: bool
    joined_at: Optional[datetime] = None


class LeagueOut(ORM):
    id: int
    name: str
    tournament_id: str
    max_teams: int
    status: LeagueStatus
    roster_slots: dict[str, int]
    trade_deadline: Optional[datetime]
    created_by_id: int
    created_at: Optional[datetime] = None


class LeagueDetail(LeagueOut):
    teams: list[TeamOut]
    # Only filled in for the commissioner.
    invite_code: Optional[str] = None
    my_team_id: int


class PlayerOut(BaseModel):
    id: int
    name: str                          # in-game tag, e.g. "Faker"
    real_name: Optional[str] = None
    role: Optional[str] = None         # roster slot key: top / jungle / mid / adc / support / coach
    team_code: Optional[str] = None    # pro team name
    region: Optional[str] = None

    @classmethod
    def from_player(cls, p, team_names: dict[int, str]) -> "PlayerOut":
        return cls(id=p.id, name=p.tag, real_name=p.name,
                   role=p.position.value if p.position else None,
                   team_code=team_names.get(p.team),
                   region=p.region.value if p.region else None)


class RosterEntry(BaseModel):
    player: PlayerOut
    acquired_via: str
    acquired_at: Optional[datetime]


class RosterOut(BaseModel):
    team: TeamOut
    players: list[RosterEntry]


# ---------------------------------------------------------------- draft

class DraftSettings(BaseModel):
    type: Optional[DraftType] = None
    scheduled_for: Optional[datetime] = None
    seconds_per_pick: Optional[int] = Field(None, ge=10, le=24 * 3600)


class DraftPickOut(ORM):
    overall_pick: int
    round_number: int
    team_id: int
    player_id: Optional[int]
    is_autopick: bool
    picked_at: Optional[datetime]


class DraftOut(BaseModel):
    id: int
    type: DraftType
    status: DraftStatus
    scheduled_for: Optional[datetime]
    seconds_per_pick: int
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    total_rounds: int
    on_the_clock_team_id: Optional[int]
    current_pick: Optional[int]
    pick_deadline: Optional[datetime]
    picks: list[DraftPickOut]


class MakePick(BaseModel):
    player_id: int


# ---------------------------------------------------------------- trades

class TradeCreate(BaseModel):
    receiver_team_id: int
    give_player_ids: list[int] = Field(min_length=1, max_length=5)
    receive_player_ids: list[int] = Field(min_length=1, max_length=5)
    message: Optional[str] = Field(None, max_length=500)


class TradeItemOut(ORM):
    from_team_id: int
    player_id: int


class TradeOut(ORM):
    id: int
    league_id: int
    proposer_team_id: int
    receiver_team_id: int
    status: TradeStatus
    message: Optional[str]
    created_at: Optional[datetime] = None
    responded_at: Optional[datetime]
    completed_at: Optional[datetime]
    items: list[TradeItemOut]
