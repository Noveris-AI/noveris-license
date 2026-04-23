from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings

PROJECT_ROOT = Path(__file__).resolve().parents[3]

settings.auto_create_tables = False
settings.database_url = "sqlite://"
settings.license_private_key_path = str(PROJECT_ROOT / "keys" / "private.pem")
settings.license_public_key_path = str(PROJECT_ROOT / "keys" / "public.pem")
settings.session_secure = False

from app.main import app  # noqa: E402
from app.modules.issue.models import Base, get_db  # noqa: E402


class InMemoryRedis:
    def __init__(self):
        self.store: dict[str, object] = {}

    def hset(self, key: str, mapping: dict[str, str]):
        self.store[key] = dict(mapping)

    def expire(self, key: str, ttl: int):
        del ttl
        return True

    def hgetall(self, key: str):
        value = self.store.get(key, {})
        return dict(value) if isinstance(value, dict) else {}

    def delete(self, key: str):
        self.store.pop(key, None)

    def get(self, key: str):
        value = self.store.get(key)
        return None if value is None else str(value)

    def exists(self, key: str):
        return key in self.store

    def setex(self, key: str, ttl: int, value: object):
        del ttl
        self.store[key] = value

    def incr(self, key: str):
        current = int(self.store.get(key, 0))
        current += 1
        self.store[key] = current
        return current

    def flushall(self):
        self.store.clear()


SQLALCHEMY_DATABASE_URL = "sqlite://"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function", autouse=True)
def fake_redis(monkeypatch):
    fake = InMemoryRedis()
    monkeypatch.setattr("app.core.session.redis_client", fake)
    yield fake


@pytest.fixture(scope="function")
def db():
    Base.metadata.create_all(bind=engine)
    db_session = TestingSessionLocal()
    try:
        yield db_session
    finally:
        db_session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db):
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
