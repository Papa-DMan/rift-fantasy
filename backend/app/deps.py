import os
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from db import DBManager, DBConfig
from models import League, FantasyTeam as Team, User
from security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
dbc = DBConfig(
    database=os.getenv("POSTGRES_DB", "lolesports_fantasy"),
    host=os.getenv("POSTGRES_HOST", "db"),
    port=int(os.getenv("POSTGRES_PORT", "5432")),
    password=os.getenv("POSTGRES_PASSWORD", "qwerpoiu"),
    user=os.getenv("POSTGRES_USER", "postgres"),
)
# Connected on first request, so importing the app (tests, scripts) doesn't
# need the database to be up.
dbm: DBManager | None = None


def get_db():
    global dbm
    if dbm is None:
        dbm = DBManager(conf=dbc)
    yield from dbm.get_async_session()


DB = Annotated[Session, Depends(get_db)]


def get_current_user(db: DB, token: Annotated[str, Depends(oauth2_scheme)]) -> User:
    user_id = decode_access_token(token)
    user = db.get(User, user_id) if user_id is not None else None
    if user is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_league_or_404(db: Session, league_id: int) -> League:
    league = db.get(League, league_id)
    if league is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "League not found")
    return league


def get_my_team(db: Session, league_id: int, user: User) -> Team:
    """The caller's team in this league. Non-members get a 404 so private
    leagues don't leak their existence."""
    team = db.scalar(select(Team).where(Team.league_id == league_id, Team.user_id == user.id))
    if team is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "League not found")
    return team


def require_commissioner(team: Team) -> None:
    if not team.is_commissioner:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the commissioner can do that")
