"""Application configuration loaded from environment variables."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Writtly API"
    environment: str = "development"
    debug: bool = True
    api_v1_prefix: str = "/api/v1"
    # When true, tables are created on startup if missing (idempotent).
    # Handy for a first boot on a fresh RDS; safe to leave on.
    create_tables_on_startup: bool = True

    secret_key: str = "change-me"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 14

    database_url: str = "sqlite+aiosqlite:///./libradesk.db"
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    # --- Twilio SMS (set these in .env; never commit real values) ---
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from_number: str = ""
    sms_enabled: bool = True          # master switch
    sms_default_country_code: str = "+91"

    # --- S3 storage (logos + receipts) ---
    s3_bucket: str = ""                     # e.g. writtly-assets
    s3_region: str = "ap-south-1"
    # Public base URL for stored files. Leave blank to use the S3 default.
    s3_public_base_url: str = ""
    # Public base for short receipt links, e.g. https://api.writtly.in
    public_base_url: str = "http://localhost:8000"

    @property
    def s3_configured(self) -> bool:
        return bool(self.s3_bucket)

    @property
    def sms_configured(self) -> bool:
        return bool(self.twilio_account_sid and self.twilio_auth_token and self.twilio_from_number)

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
