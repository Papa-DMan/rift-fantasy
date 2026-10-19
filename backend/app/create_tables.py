"""Create the fantasy tables (dev convenience; use Alembic in production).

    python -m app.create_tables            # fantasy tables only
    python -m app.create_tables --stubs    # also create stub player/round tables
"""
import sys

from app import lolesports, models  # noqa: F401
from app.db import Base, engine

if __name__ == "__main__":
    tables = None
    if "--stubs" not in sys.argv:
        tables = [t for name, t in Base.metadata.tables.items() if name not in ("player", "round")]
    Base.metadata.create_all(engine, tables=tables)
    print("created:", ", ".join(sorted(t.name for t in (tables or Base.metadata.sorted_tables))))
