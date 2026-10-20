from typing import Optional

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import or_, select

from deps import DB, CurrentUser, get_league_or_404, get_my_team
from models import Trade, TradeStatus
from schemas import TradeCreate, TradeOut
from services import trades as svc

router = APIRouter(prefix="/leagues/{league_id}/trades", tags=["trades"])


def _trade_or_404(db, league_id: int, trade_id: int) -> Trade:
    trade = db.get(Trade, trade_id, with_for_update=True)
    if trade is None or trade.league_id != league_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Trade not found")
    return trade


@router.post("", response_model=TradeOut, status_code=status.HTTP_201_CREATED)
def propose_trade(league_id: int, body: TradeCreate, db: DB, user: CurrentUser):
    me = get_my_team(db, league_id, user)
    league = get_league_or_404(db, league_id)
    trade = svc.propose(db, league, me, body.receiver_team_id,
                        body.give_player_ids, body.receive_player_ids, body.message)
    db.commit()
    return trade


@router.get("", response_model=list[TradeOut])
def list_trades(league_id: int, db: DB, user: CurrentUser,
                status_filter: Optional[TradeStatus] = None, mine: bool = False):
    """Trades in the league, newest first. Friends-only leagues show every
    trade to every member; pass `mine=true` for just your own."""
    me = get_my_team(db, league_id, user)
    stmt = select(Trade).where(Trade.league_id == league_id).order_by(Trade.id.desc())
    if status_filter:
        stmt = stmt.where(Trade.status == status_filter)
    if mine:
        stmt = stmt.where(or_(Trade.proposer_team_id == me.id, Trade.receiver_team_id == me.id))
    return db.scalars(stmt).all()


@router.get("/{trade_id}", response_model=TradeOut)
def get_trade(league_id: int, trade_id: int, db: DB, user: CurrentUser):
    get_my_team(db, league_id, user)
    return _trade_or_404(db, league_id, trade_id)


@router.post("/{trade_id}/accept", response_model=TradeOut)
def accept_trade(league_id: int, trade_id: int, db: DB, user: CurrentUser):
    me = get_my_team(db, league_id, user)
    league = get_league_or_404(db, league_id)
    trade = svc.accept(db, league, _trade_or_404(db, league_id, trade_id), me)
    db.commit()
    return trade


@router.post("/{trade_id}/reject", response_model=TradeOut)
def reject_trade(league_id: int, trade_id: int, db: DB, user: CurrentUser):
    me = get_my_team(db, league_id, user)
    trade = svc.reject(_trade_or_404(db, league_id, trade_id), me)
    db.commit()
    return trade


@router.post("/{trade_id}/cancel", response_model=TradeOut)
def cancel_trade(league_id: int, trade_id: int, db: DB, user: CurrentUser):
    me = get_my_team(db, league_id, user)
    trade = svc.cancel(_trade_or_404(db, league_id, trade_id), me)
    db.commit()
    return trade
