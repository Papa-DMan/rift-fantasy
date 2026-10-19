import secrets
from typing import Optional

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.deps import DB, CurrentUser, get_league_or_404, get_my_team, require_commissioner
from app.lolesports import Player, player_position, team_names
from app.models import Draft, League, LeagueStatus, Team, TeamPlayer
from app.schemas import (
    JoinLeague, LeagueCreate, LeagueDetail, LeagueOut, LeagueUpdate, PlayerOut,
    RosterEntry, RosterOut, TeamOut,
)
from app.services.draft import available_players

router = APIRouter(prefix="/leagues", tags=["leagues"])

# No 0/O/1/I/L so codes are easy to read out to friends.
INVITE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def new_invite_code(db) -> str:
    while True:
        code = "".join(secrets.choice(INVITE_ALPHABET) for _ in range(8))
        if db.scalar(select(League.id).where(League.invite_code == code)) is None:
            return code


def league_detail(league: League, me: Team) -> LeagueDetail:
    out = LeagueDetail.model_validate(
        {**LeagueOut.model_validate(league).model_dump(),
         "teams": [TeamOut.model_validate(t) for t in league.teams],
         "my_team_id": me.id}
    )
    if me.is_commissioner:
        out.invite_code = league.invite_code
    return out


@router.post("", response_model=LeagueDetail, status_code=status.HTTP_201_CREATED)
def create_league(body: LeagueCreate, db: DB, user: CurrentUser):
    league = League(
        name=body.name.strip(),
        tournament_id=body.tournament_id or settings.default_tournament_id,
        invite_code=new_invite_code(db),
        max_teams=body.max_teams,
        roster_slots=body.roster_slots,
        scoring_rules={},  # scoring is TBD
        trade_deadline=body.trade_deadline,
        created_by_id=user.id,
        status=LeagueStatus.SETUP,
    )
    db.add(league)
    db.flush()
    me = Team(league_id=league.id, user_id=user.id, name=body.team_name.strip(),
              is_commissioner=True)
    db.add_all([me, Draft(league_id=league.id)])
    db.commit()
    db.refresh(league)
    return league_detail(league, me)


@router.get("", response_model=list[LeagueOut])
def my_leagues(db: DB, user: CurrentUser):
    return db.scalars(
        select(League).join(Team).where(Team.user_id == user.id).order_by(League.id)
    ).all()


@router.post("/join", response_model=LeagueDetail, status_code=status.HTTP_201_CREATED)
def join_league(body: JoinLeague, db: DB, user: CurrentUser):
    league = db.scalar(select(League).where(League.invite_code == body.invite_code.strip().upper()))
    if league is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Invalid invite code")
    if league.status != LeagueStatus.SETUP:
        raise HTTPException(status.HTTP_409_CONFLICT, "This league has already drafted")
    if any(t.user_id == user.id for t in league.teams):
        raise HTTPException(status.HTTP_409_CONFLICT, "You're already in this league")
    team_count = db.scalar(select(func.count()).select_from(Team).where(Team.league_id == league.id))
    if team_count >= league.max_teams:
        raise HTTPException(status.HTTP_409_CONFLICT, "This league is full")

    me = Team(league_id=league.id, user_id=user.id, name=body.team_name.strip())
    db.add(me)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "That team name is taken in this league")
    db.refresh(league)
    return league_detail(league, me)


@router.get("/{league_id}", response_model=LeagueDetail)
def get_league(league_id: int, db: DB, user: CurrentUser):
    me = get_my_team(db, league_id, user)
    return league_detail(get_league_or_404(db, league_id), me)


@router.patch("/{league_id}", response_model=LeagueDetail)
def update_league(league_id: int, body: LeagueUpdate, db: DB, user: CurrentUser):
    me = get_my_team(db, league_id, user)
    require_commissioner(me)
    league = get_league_or_404(db, league_id)
    changes = body.model_dump(exclude_unset=True)
    if league.status != LeagueStatus.SETUP and ({"roster_slots", "max_teams"} & changes.keys()):
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "Roster slots and team count are locked once the draft starts")
    if "max_teams" in changes and changes["max_teams"] < len(league.teams):
        raise HTTPException(status.HTTP_409_CONFLICT, "League already has more teams than that")
    for field, value in changes.items():
        setattr(league, field, value)
    db.commit()
    db.refresh(league)
    return league_detail(league, me)


@router.post("/{league_id}/invite-code", response_model=LeagueDetail)
def rotate_invite_code(league_id: int, db: DB, user: CurrentUser):
    """Issue a new invite code; the old one stops working."""
    me = get_my_team(db, league_id, user)
    require_commissioner(me)
    league = get_league_or_404(db, league_id)
    league.invite_code = new_invite_code(db)
    db.commit()
    return league_detail(league, me)


@router.post("/{league_id}/leave", status_code=status.HTTP_204_NO_CONTENT)
def leave_league(league_id: int, db: DB, user: CurrentUser):
    me = get_my_team(db, league_id, user)
    league = get_league_or_404(db, league_id)
    if league.status != LeagueStatus.SETUP:
        raise HTTPException(status.HTTP_409_CONFLICT, "You can't leave after the draft starts")
    if me.is_commissioner:
        raise HTTPException(status.HTTP_409_CONFLICT, "The commissioner can't leave their league")
    db.delete(me)
    db.commit()


@router.get("/{league_id}/teams/{team_id}/roster", response_model=RosterOut)
def team_roster(league_id: int, team_id: int, db: DB, user: CurrentUser):
    get_my_team(db, league_id, user)
    team = db.get(Team, team_id)
    if team is None or team.league_id != league_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Team not found")
    rows = db.execute(
        select(TeamPlayer, Player).join(Player, Player.id == TeamPlayer.player_id)
        .where(TeamPlayer.team_id == team_id).order_by(TeamPlayer.acquired_at)
    ).all()
    names = team_names(db, [p for _, p in rows])
    return RosterOut(
        team=TeamOut.model_validate(team),
        players=[RosterEntry(player=PlayerOut.from_player(p, names), acquired_via=tp.acquired_via.value,
                             acquired_at=tp.acquired_at) for tp, p in rows],
    )


@router.get("/{league_id}/players", response_model=list[PlayerOut])
def league_players(league_id: int, db: DB, user: CurrentUser,
                   available: bool = True, position: Optional[str] = None):
    """Players in the pool. `available=true` (default) hides anyone already on
    a team in this league; `position` filters by slot key (top, mid, ...)."""
    get_my_team(db, league_id, user)
    if available:
        players = available_players(db, league_id, position)
    else:
        players = db.scalars(select(Player).order_by(Player.id)).all()
        if position:
            players = [p for p in players if player_position(p) == position]
    names = team_names(db, players)
    return [PlayerOut.from_player(p, names) for p in players]
