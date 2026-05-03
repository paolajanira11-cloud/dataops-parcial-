import os

os.environ.setdefault("TIENDA_DATABASE_URL", "sqlite:///:memory:")

import pytest
from sqlmodel import SQLModel
from fastapi.testclient import TestClient

from app.database import engine
from app.main import app


@pytest.fixture
def client():
    SQLModel.metadata.drop_all(engine)
    with TestClient(app) as c:
        yield c
