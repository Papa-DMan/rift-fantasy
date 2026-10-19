import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv(
        "DATABASE_URL", "postgresql+psycopg://postgres@localhost:5432/fantasy"
    )
    # MUST be overridden in any real deployment.
    jwt_secret: str = os.getenv("JWT_SECRET", "dev-only-insecure-secret-change-me-in-prod")
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = int(os.getenv("ACCESS_TOKEN_MINUTES", "10080"))  # 7 days
    # Default Worlds tournament id used when a league doesn't specify one.
    default_tournament_id: str = os.getenv("DEFAULT_TOURNAMENT_ID", "worlds-2026")


settings = Settings()
