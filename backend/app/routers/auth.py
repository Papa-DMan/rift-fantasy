from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from deps import DB, CurrentUser
from models import User
from schemas import Token, UserCreate, UserOut
from security import create_access_token, hash_password, verify_password

router = APIRouter(tags=["auth"])


@router.post("/auth/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(body: UserCreate, db: DB):
    user = User(email=body.email.lower(), display_name=body.display_name.strip(),
                pw_hash=hash_password(body.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with that email already exists")
    return user


@router.post("/auth/login", response_model=Token)
def login(form: Annotated[OAuth2PasswordRequestForm, Depends()], db: DB):
    """Standard OAuth2 password form: send `username` (the email) and `password`
    as form fields. Returns a bearer token for the Authorization header."""
    user = db.scalar(select(User).where(User.email == form.username.lower()))
    if user is None or not verify_password(form.password, user.pw_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong email or password",
                            headers={"WWW-Authenticate": "Bearer"})
    return Token(access_token=create_access_token(user.id))


@router.get("/users/me", response_model=UserOut)
def me(user: CurrentUser):
    return user
