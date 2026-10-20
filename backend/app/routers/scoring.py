from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from db import Round
from deps import DB, CurrentUser, get_league_or_404, get_my_team
from lolesports import Player, team_names
from models import FantasyTeam as Team
from schemas import (
    GamePointsOut, LineupSlotOut, PlayerOut, RoundOut, StandingRow, StandingsOut, TeamOut, TeamRoundOut,
)
from services.scoring import (
    all_rounds, draft_completed_at, effective_rules, games_by_round, round_status, standings,
    team_round,
)

router = APIRouter(prefix="/leagues/{league_id}", tags=["scoring"])


@router.get("/standings", response_model=StandingsOut)
def league_standings(league_id: int, db: DB, user: CurrentUser):
    """Every round with its status, and each team's points per counted round
    plus its season total, best first."""
    get_my_team(db, league_id, user)
    league = get_league_or_404(db, league_id)
    rounds, teams = standings(db, league)
    return StandingsOut(rounds=[RoundOut(**r) for r in rounds],
                        teams=[StandingRow(**t) for t in teams],
                        scoring_rules=effective_rules(league))


@router.get("/teams/{team_id}/rounds/{round_id}", response_model=TeamRoundOut)
def team_round_detail(league_id: int, team_id: int, round_id: int, db: DB, user: CurrentUser):
    """A team's lineup for one round with points per player and per game."""
    get_my_team(db, league_id, user)
    league = get_league_or_404(db, league_id)
    team = db.get(Team, team_id)
    if team is None or team.league_id != league_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Team not found")
    rnd = db.get(Round, round_id)
    if rnd is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Round not found")

    rounds = all_rounds(db)
    games = games_by_round(db, rounds)[rnd.id]
    drafted_at = draft_completed_at(db, league)
    round_state = round_status(rnd, games, drafted_at)
    counts = round_state in ("live", "final")
    total, slots = team_round(db, league, team_id, rnd, games if counts else [], effective_rules(league),
                              persist=counts)

    players = {p.id: p for p in db.scalars(select(Player).where(Player.id.in_([s.slot.player_id for s in slots])))}
    names = team_names(db, players.values())
    return TeamRoundOut(
        team=TeamOut.model_validate(team),
        round=RoundOut(id=rnd.id, name=rnd.name, stage=rnd.stage.value, lock_at=rnd.lock_at,
                       ends_at=rnd.ends_at, status=round_state),
        total=total,
        lineup=[LineupSlotOut(
            slot=s.slot.slot.value, slot_index=s.slot.slot_index,
            player=PlayerOut.from_player(players[s.slot.player_id], names),
            points=s.points, counts=s.counts,
            games=[GamePointsOut(game_id=g.game_id, points=g.points, breakdown=g.breakdown) for g in s.games],
        ) for s in slots],
    )
