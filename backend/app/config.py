from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    app_env: str = "development"
    log_level: str = "INFO"

    # Postgres
    postgres_host: str = "postgres"
    postgres_port: int = 5432
    postgres_db: str = "mt5bridge"
    postgres_user: str = "mt5bridge"
    postgres_password: str = "changeme"

    # Redis
    redis_host: str = "redis"
    redis_port: int = 6379
    redis_password: str = "changeme"
    redis_db: int = 0

    # JWT
    jwt_secret_key: str = "changeme-generate-with-openssl-rand-hex-32"
    jwt_algorithm: str = "HS256"
    jwt_access_token_ttl_minutes: int = 15
    jwt_refresh_token_ttl_days: int = 7

    # Order confirmation anti-replay
    order_token_ttl_seconds: int = 60

    # Kotak Neo — via the official `neo-api-client` SDK (confirmed against v2.0.0).
    # consumer_key/neo_fin_key/ucc/mobile_number are static per-app/per-account identifiers
    # and belong in .env. TOTP and MPIN are NOT static secrets — the SDK's totp_login/
    # totp_validate flow requires them fresh on every login, so they are never stored here;
    # they're supplied per-call to POST /auth/kotak-login (see routers/auth.py).
    kotak_neo_environment: str = "prod"  # "prod" or "uat"
    kotak_neo_consumer_key: str = ""
    kotak_neo_consumer_secret: str = ""  # optional per SDK; not required for totp_login/totp_validate
    kotak_neo_neo_fin_key: str = ""
    kotak_neo_ucc: str = ""
    kotak_neo_mobile_number: str = ""
    kotak_neo_poll_interval_seconds: float = 5.0

    # Explicit, auditable kill-switch placeholder — see docs/SECURITY.md.
    # Nothing in this codebase currently reads this flag to enable automation.
    automated_trading_enabled: bool = False

    tick_retention_days: int = 90

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def redis_url(self) -> str:
        auth = f":{self.redis_password}@" if self.redis_password else ""
        return f"redis://{auth}{self.redis_host}:{self.redis_port}/{self.redis_db}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
