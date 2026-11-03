from pathlib import Path

import pytest

from app.database import build_database
from app.policies import sections_from_json
from app.tools import StoreTools, ToolContext


@pytest.fixture
def db(tmp_path):
    root = Path(__file__).resolve().parents[1]
    path = tmp_path / "store.db"
    build_database(path, root / "fixtures", sections_from_json(root / "fixtures/demo_policies.json"))
    return path


@pytest.fixture
def tools(db):
    return StoreTools(ToolContext(db))
