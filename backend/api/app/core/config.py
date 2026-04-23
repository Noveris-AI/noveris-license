from typing import Annotated, Optional
from urllib.parse import quote

from pydantic import AliasChoices, Field, PrivateAttr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
    _database_url_override: Optional[str] = PrivateAttr(default=None)
    _redis_url_override: Optional[str] = PrivateAttr(default=None)

    # App
    app_name: str = "naviam-license"
    debug: bool = False
    auto_create_tables: bool = True

    # Database
    database_type: str = "postgresql+psycopg"
    database_host: str = "localhost"
    database_port: int = 5432
    database_username: str = "naviam_postgres"
    database_password: str = "Postgres@!QAZxsw2."
    database_name: str = "naviam_postgres"

    # Redis (for sessions & rate limiting)
    redis_type: str = "redis"
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_username: str = "naviam_redis"
    redis_password: str = "Redis@!QAZxsw2."
    redis_db: int = 0

    # Session
    session_cookie_name: str = "naviam_session"
    session_max_age: int = 28800  # 8 hours in seconds
    session_secure: bool = False  # Set True in production (HTTPS only)
    session_httponly: bool = True
    session_samesite: str = "lax"

    # CORS
    allowed_origins: Annotated[list[str], NoDecode] = Field(
        default=["http://localhost:5173", "http://localhost:3000"],
        validation_alias=AliasChoices("ALLOWED_ORIGINS"),
    )

    # Signing keys
    license_signing_key_id: str = "naviam-license-v2"
    license_private_key_path: str = Field(
        "/app/keys/private.pem",
        validation_alias=AliasChoices("LICENSE_PRIVATE_KEY_PATH", "RSA_PRIVATE_KEY_PATH"),
    )
    license_public_key_path: str = Field(
        "/app/keys/public.pem",
        validation_alias=AliasChoices("LICENSE_PUBLIC_KEY_PATH", "RSA_PUBLIC_KEY_PATH"),
    )
    license_private_key_pem: Optional[str] = None
    license_public_key_pem: Optional[str] = None

    # Lease defaults
    online_lease_ttl_hours: int = 24
    offline_lease_ttl_days: int = 30
    license_grace_period_days: int = 7
    proof_tolerance_seconds: int = 600

    # Rate limiting
    verify_rate_limit: int = 100  # requests per window
    verify_rate_window: int = 60  # seconds
    login_rate_limit: int = 5  # login attempts per window
    login_rate_window: int = 300  # seconds
    offline_process_rate_limit: int = 30  # offline process requests per operator per window
    offline_process_rate_window: int = 60  # seconds

    # Offline request bundles
    offline_request_ttl_seconds: int = 900  # 15 minutes

    # Suspicious activity detection
    suspicious_ip_threshold: int = 2  # distinct activation IPs in 24h

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_origins(cls, value):
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @property
    def database_url(self) -> str:
        if self._database_url_override:
            return self._database_url_override
        username = quote(self.database_username, safe="")
        password = quote(self.database_password, safe="")
        database_name = quote(self.database_name, safe="")
        return f"{self.database_type}://{username}:{password}@{self.database_host}:{self.database_port}/{database_name}"

    @database_url.setter
    def database_url(self, value: str) -> None:
        self._database_url_override = value

    @property
    def redis_url(self) -> str:
        if self._redis_url_override:
            return self._redis_url_override
        username = quote(self.redis_username, safe="")
        password = quote(self.redis_password, safe="")
        return f"{self.redis_type}://{username}:{password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"

    @redis_url.setter
    def redis_url(self, value: str) -> None:
        self._redis_url_override = value

settings = Settings()
