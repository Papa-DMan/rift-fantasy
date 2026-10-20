"""Create every table: the lolesports ones from ../db.py and the fantasy ones
from app/models.py (dev convenience; use Alembic in production). Existing
tables are left alone.

    python -m app.create_tables            # tables only
    python -m app.create_tables --seed     # also run db.seed(): Worlds rounds,
                                           # teams, players, and games from the
                                           # lolesports API (needs network)
"""
import sys

from app import models  # noqa: F401  (register the fantasy tables)
from db import Base, SessionLocal, engine

if __name__ == "__main__":
    Base.metadata.create_all(engine)
    print("tables:", ", ".join(sorted(Base.metadata.tables)))
    if "--seed" in sys.argv:
        import db
        with SessionLocal() as session:
            db.seed(session)
        print("seeded Worlds rounds, teams, players and games")
