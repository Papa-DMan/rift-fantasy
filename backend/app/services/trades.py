"""Trade logic.

A trade is proposed by one team to another, and the receiver accepts or
rejects it. Accepting swaps ownership immediately (status COMPLETED). The
ACCEPTED and VETOED statuses in the schema are left for a later
commissioner-review / veto window.

Ownership is re-checked at accept time, because rosters can change between
proposal and acceptance (another trade, a drop). Any other pending trade that
involves a player who just moved is cancelled.
"""
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.lolesports import Player, player_position
from app.models import (
    AcquisitionType, League, LeagueStatus, Team, TeamPlayer, Trade, TradeItem, TradeStatus,
)
from app.services.roster import as_utc, roster_fits, utcnow

OPEN_STATUSES = (TradeStatus.PROPOSED,)


def _check_trading_open(league: League) -> None:
    if league.status != LeagueStatus.ACTIVE:
        raise HTTPException(status.HTTP_409_CONFLICT, "Trading opens after the draft")
    deadline = as_utc(league.trade_deadline)
    if deadline is not None and utcnow() > deadline:
        raise HTTPException(status.HTTP_409_CONFLICT, "The trade deadline has passed")


def _ownership(db: Session, league_id: int, player_ids: list[int]) -> dict[int, TeamPlayer]:
    rows = db.scalars(select(TeamPlayer).where(
        TeamPlayer.league_id == league_id, TeamPlayer.player_id.in_(player_ids)))
    return {r.player_id: r for r in rows}


def _validate(db: Session, league: League, proposer_id: int, receiver_id: int,
              give: list[int], receive: list[int]) -> dict[int, TeamPlayer]:
    """Both sides still own what they're offering, and both rosters still fit
    afterwards. Returns the ownership rows keyed by player id."""
    if set(give) & set(receive) or len(set(give)) != len(give) or len(set(receive)) != len(receive):
        raise HTTPException(422, "Duplicate players in trade")
    owned = _ownership(db, league.id, give + receive)
    for pid in give:
        if pid not in owned or owned[pid].team_id != proposer_id:
            raise HTTPException(status.HTTP_409_CONFLICT,
                                f"Player {pid} is not on the proposing team")
    for pid in receive:
        if pid not in owned or owned[pid].team_id != receiver_id:
            raise HTTPException(status.HTTP_409_CONFLICT,
                                f"Player {pid} is not on the receiving team")

    def positions_after(team_id: int, out: list[int], incoming: list[int]) -> list:
        keep = db.scalars(select(TeamPlayer.player_id).where(
            TeamPlayer.team_id == team_id, TeamPlayer.player_id.not_in(out))).all()
        players = db.scalars(select(Player).where(Player.id.in_(list(keep) + incoming))).all()
        return [player_position(p) for p in players]

    if not roster_fits(positions_after(proposer_id, give, receive), league.roster_slots):
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "The proposing team's roster wouldn't fit after this trade")
    if not roster_fits(positions_after(receiver_id, receive, give), league.roster_slots):
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "The receiving team's roster wouldn't fit after this trade")
    return owned


def propose(db: Session, league: League, proposer: Team, receiver_team_id: int,
            give: list[int], receive: list[int], message: str | None) -> Trade:
    _check_trading_open(league)
    receiver = db.get(Team, receiver_team_id)
    if receiver is None or receiver.league_id != league.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Team not found in this league")
    if receiver.id == proposer.id:
        raise HTTPException(422, "You can't trade with yourself")
    _validate(db, league, proposer.id, receiver.id, give, receive)

    trade = Trade(league_id=league.id, proposer_team_id=proposer.id,
                  receiver_team_id=receiver.id, message=message,
                  status=TradeStatus.PROPOSED)
    trade.items = ([TradeItem(from_team_id=proposer.id, player_id=p) for p in give]
                   + [TradeItem(from_team_id=receiver.id, player_id=p) for p in receive])
    db.add(trade)
    db.flush()
    return trade


def _sides(trade: Trade) -> tuple[list[int], list[int]]:
    give = [i.player_id for i in trade.items if i.from_team_id == trade.proposer_team_id]
    receive = [i.player_id for i in trade.items if i.from_team_id == trade.receiver_team_id]
    return give, receive


def _require_open(trade: Trade) -> None:
    if trade.status not in OPEN_STATUSES:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            f"Trade is already {trade.status.value}")


def accept(db: Session, league: League, trade: Trade, team: Team) -> Trade:
    if team.id != trade.receiver_team_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the receiving team can accept")
    _require_open(trade)
    _check_trading_open(league)
    give, receive = _sides(trade)
    owned = _validate(db, league, trade.proposer_team_id, trade.receiver_team_id, give, receive)

    now = utcnow()
    for pid in give:
        row = owned[pid]
        row.team_id, row.acquired_via, row.acquired_at = trade.receiver_team_id, AcquisitionType.TRADE, now
    for pid in receive:
        row = owned[pid]
        row.team_id, row.acquired_via, row.acquired_at = trade.proposer_team_id, AcquisitionType.TRADE, now
    trade.status = TradeStatus.COMPLETED
    trade.responded_at = trade.completed_at = now

    # Other open offers that include any of these players can no longer happen.
    stale = db.scalars(
        select(Trade).join(TradeItem).where(
            Trade.league_id == league.id, Trade.id != trade.id,
            Trade.status.in_(OPEN_STATUSES), TradeItem.player_id.in_(give + receive),
        ).distinct()
    ).all()
    for t in stale:
        t.status = TradeStatus.CANCELLED
        t.responded_at = now
    db.flush()
    return trade


def reject(trade: Trade, team: Team) -> Trade:
    if team.id != trade.receiver_team_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the receiving team can reject")
    _require_open(trade)
    trade.status = TradeStatus.REJECTED
    trade.responded_at = utcnow()
    return trade


def cancel(trade: Trade, team: Team) -> Trade:
    if team.id != trade.proposer_team_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the proposing team can cancel")
    _require_open(trade)
    trade.status = TradeStatus.CANCELLED
    trade.responded_at = utcnow()
    return trade
