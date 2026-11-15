from functools import lru_cache
from uuid import UUID

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://hospital:hospital@localhost:5432/hospital_agent"
    session_hash_key: str = Field(min_length=32)
    demo_staff_username: str = "demo_staff"
    demo_staff_password: str = Field(min_length=12)
    synthetic_tenant_id: UUID = UUID("00000000-0000-4000-8000-000000000001")
    session_ttl_hours: int = Field(default=24, ge=1, le=168)


@lru_cache
def get_settings() -> Settings:
    return Settings()

