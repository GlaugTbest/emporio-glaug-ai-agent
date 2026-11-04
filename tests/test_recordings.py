import sqlite3
from contextlib import closing

import pytest

from app.evaluation import require_demo_database
from scripts.capture_examples import recorded_scenario


def test_public_recording_accepts_only_exact_fictional_data(db):
    require_demo_database(db)
    with closing(sqlite3.connect(db)) as conn, conn:
        conn.execute("UPDATE customers SET email=? WHERE customer_id=1", ("private-data@example.invalid",))
    with pytest.raises(ValueError, match="fictional"):
        require_demo_database(db)


def test_recorded_transcript_rejects_a_different_question():
    scenario = {"id": 1, "title": "test", "why_this_matters": "test", "customer_context": None,
                "turns": ["Which instrument?"], "case_ids": ["catalog"]}
    evaluation = {"mode": "REAL_OLLAMA_PLANNING_PYTHON_FACTS", "dataset": "public_fixtures", "model": "test:local",
                  "results": [{"case": "catalog", "passed": True, "user": "Different question", "customer_context": None}]}
    with pytest.raises(ValueError, match="question"):
        recorded_scenario(scenario, evaluation, "test:local")


def test_recorded_transcript_rejects_nonpublic_dataset():
    with pytest.raises(ValueError, match="public"):
        recorded_scenario({}, {"dataset": "private"}, "test:local")
