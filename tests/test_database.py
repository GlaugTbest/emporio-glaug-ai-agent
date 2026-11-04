import csv
import os
import sqlite3
from pathlib import Path

import pytest

from app.database import build_database, read_only_connection
from app.policies import sections_from_json, sections_from_pdf


def test_import_counts_and_foreign_keys(db):
    with read_only_connection(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 7
        assert conn.execute("SELECT COUNT(*) FROM promotions").fetchone()[0] == 4
        assert conn.execute("SELECT COUNT(*) FROM order_items").fetchone()[0] == 3
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        with pytest.raises(sqlite3.DatabaseError):
            conn.execute("DELETE FROM products")


def test_import_failure_keeps_old_db(db, tmp_path):
    root = Path(__file__).resolve().parents[1]
    copies = tmp_path / "broken"
    copies.mkdir()
    for f in (root / "fixtures").glob("*.csv"):
        (copies / f.name).write_bytes(f.read_bytes())
    rows = list(csv.DictReader((copies / "order_items.csv").open()))
    rows[0]["product_id"] = "9999"  # broken foreign key
    with (copies / "order_items.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(sqlite3.IntegrityError):
        build_database(db, copies, sections_from_json(root / "fixtures/demo_policies.json"))
    with read_only_connection(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM order_items").fetchone()[0] == 3


def test_pdf_extraction_original_available():
    manual = os.getenv("ARTEFACT_POLICY_PDF")
    if not manual:
        pytest.skip("Set ARTEFACT_POLICY_PDF to test the original local manual")
    pages = sections_from_pdf(Path(manual))
    assert len(pages) == 8
    assert any("7 (sete) dias" in p["content"] for p in pages)


def test_read_only_context_releases_the_connection(tmp_path):
    path = tmp_path / "minimal.db"
    conn = sqlite3.connect(path)
    conn.close()
    with read_only_connection(path) as opened:
        assert opened.execute("SELECT 1").fetchone()[0] == 1
    with pytest.raises(sqlite3.ProgrammingError):
        opened.execute("SELECT 1")


def test_import_publishes_closed_database_without_temporary_files(tmp_path):
    root = Path(__file__).resolve().parents[1]
    path = tmp_path / "store.db"
    build_database(path, root / "fixtures", sections_from_json(root / "fixtures/demo_policies.json"))
    path.rename(tmp_path / "renamed.db")
    assert sorted(p.name for p in tmp_path.iterdir()) == ["renamed.db"]
