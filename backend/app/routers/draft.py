from typing import Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.deps import DB, CurrentUser, get_league_or_404, get_my_team, require_commissioner
from app.models import Draft, DraftStatus
from app.schemas import DraftOut, DraftPickOut, DraftSettings, MakePick
from app.services import draft as svc
from app.services.roster import roster_size

router = APIRouter(prefix="/leagues/{league_id}/draft", tags=["draft"])


class StartDraft(BaseModel):
    # Team ids in first-round order. Omit for a random order.
    order: Optional[list[int]] = None


def draft_out(draft: Draft) -> DraftOut:
    cur = svc.current_pick(draft) if draft.status == DraftStatus.IN_PROGRESS else None
    return DraftOut(
        id=draft.id, type=draft.type, status=draft.status,
        scheduled_for=draft.scheduled_for, seconds_per_pick=draft.seconds_per_pick,
        started_at=draft.started_at, completed_at=draft.completed_at,
        total_rounds=roster_size(draft.league),
        on_the_clock_team_id=cur.team_id if cur else None,
        current_pick=cur.overall_pick if cur else None,
        pick_deadline=svc.pick_deadline(draft),
        picks=[DraftPickOut.model_validate(p) for p in draft.picks],
    )


@router.get("", response_model=DraftOut)
def get_draft(league_id: int, db: DB, user: CurrentUser):
    """Current draft board. Poll this during the draft; it also applies
    autopicks for anyone whose clock ran out."""
    get_my_team(db, league_id, user)
    league = get_league_or_404(db, league_id)
    draft = svc.lock_draft(db, league_id)
    if svc.process_expired_picks(db, league, draft):
        db.commit()
    return draft_out(draft)


@router.patch("", response_model=DraftOut)
def update_draft_settings(league_id: int, body: DraftSettings, db: DB, user: CurrentUser):
    require_commissioner(get_my_team(db, league_id, user))
    draft = svc.lock_draft(db, league_id)
    if draft.status != DraftStatus.SCHEDULED:
        raise HTTPException(status.HTTP_409_CONFLICT, "Draft settings are locked once it starts")
    for field, value in body.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(draft, field, value)
    db.commit()
    return draft_out(draft)


@router.post("/start", response_model=DraftOut)
def start_draft(league_id: int, db: DB, user: CurrentUser, body: Optional[StartDraft] = None):
    require_commissioner(get_my_team(db, league_id, user))
    league = get_league_or_404(db, league_id)
    draft = svc.lock_draft(db, league_id)
    svc.start_draft(db, league, draft, body.order if body else None)
    db.commit()
    return draft_out(draft)


@router.post("/pick", response_model=DraftOut)
def make_pick(league_id: int, body: MakePick, db: DB, user: CurrentUser):
    me = get_my_team(db, league_id, user)
    league = get_league_or_404(db, league_id)
    draft = svc.lock_draft(db, league_id)
    try:
        svc.make_pick(db, league, draft, me, body.player_id)
    except HTTPException:
        # Keep any autopicks that were applied before the error.
        db.commit()
        raise
    db.commit()
    return draft_out(draft)
