"""Draft logic.

Every DraftPick row is created when the draft starts (team_id set,
player_id NULL), so "whose turn is it" is just the first empty pick and the
snake/linear order is decided once.

There's no background worker: the pick timer is enforced lazily. Whenever the
draft is read or a pick is made, any picks whose clock ran out are filled by
autopick first.
"""
import random
from datetime import datetime, timedelta
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.lolesports import Player, player_position
from app.models import (
    AcquisitionType, Draft, DraftPick, DraftStatus, DraftType, League,
    LeagueStatus, Team, TeamPlayer,
)
from app.services.roster import as_utc, roster_fits, roster_size, team_positions, utcnow


def lock_draft(db: Session, league_id: int) -> Draft:
    """Row-lock the draft so two simultaneous picks can't both take the same
    slot (FOR UPDATE on Postgres; a no-op on SQLite)."""
    draft = db.scalar(select(Draft).where(Draft.league_id == league_id).with_for_update())
    if draft is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Draft not found")
    return draft


def current_pick(draft: Draft) -> Optional[DraftPick]:
    return next((p for p in draft.picks if p.player_id is None), None)


def pick_deadline(draft: Draft) -> Optional[datetime]:
    cur = current_pick(draft)
    if draft.status != DraftStatus.IN_PROGRESS or cur is None:
        return None
    prev = [p for p in draft.picks if p.overall_pick < cur.overall_pick]
    clock_started = as_utc(prev[-1].picked_at) if prev else as_utc(draft.started_at)
    return clock_started + timedelta(seconds=draft.seconds_per_pick)


def start_draft(db: Session, league: League, draft: Draft, order: Optional[list[int]]) -> None:
    if draft.status != DraftStatus.SCHEDULED or league.status != LeagueStatus.SETUP:
        raise HTTPException(status.HTTP_409_CONFLICT, "Draft has already started")
    team_ids = [t.id for t in league.teams]
    if len(team_ids) < 2:
        raise HTTPException(status.HTTP_409_CONFLICT, "Need at least two teams to draft")
    if order is not None:
        if sorted(order) != sorted(team_ids):
            raise HTTPException(422,
                                "order must list every team in the league exactly once")
    else:
        order = team_ids[:]
        random.shuffle(order)

    overall = 1
    for rnd in range(1, roster_size(league) + 1):
        seq = order if draft.type == DraftType.LINEAR or rnd % 2 == 1 else order[::-1]
        for team_id in seq:
            db.add(DraftPick(draft_id=draft.id, overall_pick=overall,
                             round_number=rnd, team_id=team_id))
            overall += 1

    draft.status = DraftStatus.IN_PROGRESS
    draft.started_at = utcnow()
    league.status = LeagueStatus.DRAFTING
    db.flush()
    db.refresh(draft)


def _owned_player_ids(db: Session, league_id: int) -> set[int]:
    return set(db.scalars(select(TeamPlayer.player_id).where(TeamPlayer.league_id == league_id)))


def available_players(db: Session, league_id: int, position: Optional[str] = None) -> list[Player]:
    owned = _owned_player_ids(db, league_id)
    players = db.scalars(select(Player).order_by(Player.id)).all()
    return [p for p in players
            if p.id not in owned and (position is None or player_position(p) == position)]


def _record_pick(db: Session, league: League, draft: Draft, pick: DraftPick,
                 player: Player, when, auto: bool) -> None:
    pick.player_id = player.id
    pick.picked_at = when
    pick.is_autopick = auto
    db.add(TeamPlayer(league_id=league.id, team_id=pick.team_id, player_id=player.id,
                      acquired_via=AcquisitionType.DRAFT, acquired_at=when))
    db.flush()
    if current_pick(draft) is None:
        draft.status = DraftStatus.COMPLETE
        draft.completed_at = when
        league.status = LeagueStatus.ACTIVE


def _autopick_player(db: Session, league: League, team_id: int) -> Optional[Player]:
    # No rankings yet, so autopick takes the first available player that fits
    # the roster. Swap in ADP / projected points once scoring exists.
    have = team_positions(db, team_id)
    candidates = available_players(db, league.id)
    for p in candidates:
        if roster_fits(have + [player_position(p)], league.roster_slots):
            return p
    return candidates[0] if candidates else None


def process_expired_picks(db: Session, league: League, draft: Draft) -> int:
    """Autopick for every pick whose clock has run out. Returns how many."""
    made = 0
    now = utcnow()
    while draft.status == DraftStatus.IN_PROGRESS:
        deadline = pick_deadline(draft)
        if deadline is None or deadline > now:
            break
        pick = current_pick(draft)
        player = _autopick_player(db, league, pick.team_id)
        if player is None:
            break  # player pool exhausted; leave it for the commissioner
        # Stamp the autopick at its deadline so the next team's clock starts
        # from when this one should have ended, not from when someone looked.
        _record_pick(db, league, draft, pick, player, deadline, auto=True)
        made += 1
    return made


def make_pick(db: Session, league: League, draft: Draft, team: Team, player_id: int) -> DraftPick:
    process_expired_picks(db, league, draft)
    if draft.status != DraftStatus.IN_PROGRESS:
        raise HTTPException(status.HTTP_409_CONFLICT, "Draft is not in progress")
    pick = current_pick(draft)
    if pick.team_id != team.id:
        raise HTTPException(status.HTTP_409_CONFLICT, "It's not your pick")
    player = db.get(Player, player_id)
    if player is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Player not found")
    if player.id in _owned_player_ids(db, league.id):
        raise HTTPException(status.HTTP_409_CONFLICT, "Player already drafted")
    if not roster_fits(team_positions(db, team.id) + [player_position(player)],
                       league.roster_slots):
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "No open roster slot for that position")
    _record_pick(db, league, draft, pick, player, utcnow(), auto=False)
    return pick
