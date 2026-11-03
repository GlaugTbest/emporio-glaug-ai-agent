"""SQLite import and read-only connection. Original challenge files stay local."""

from __future__ import annotations

import csv
import json
import sqlite3
from decimal import Decimal, InvalidOperation
from pathlib import Path

SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS categories (
    category_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS products (
    product_id INTEGER PRIMARY KEY,
    price_brl TEXT NOT NULL,
    name TEXT NOT NULL,
    category_id INTEGER NOT NULL REFERENCES categories(category_id),
    description TEXT NOT NULL,
    stock_quantity INTEGER NOT NULL CHECK (stock_quantity >= 0),
    status TEXT NOT NULL CHECK (status IN ('active', 'coming_soon', 'discontinued')),
    specs TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS customers (
    customer_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    phone TEXT NOT NULL,
    email TEXT NOT NULL,
    city TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS orders (
    order_id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(customer_id),
    order_date TEXT NOT NULL,
    status TEXT NOT NULL,
    total_brl TEXT NOT NULL,
    payment_method TEXT NOT NULL,
    tracking_code TEXT NOT NULL,
    estimated_delivery TEXT NOT NULL,
    notes TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS order_items (
    order_id INTEGER NOT NULL REFERENCES orders(order_id),
    product_id INTEGER NOT NULL REFERENCES products(product_id),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    PRIMARY KEY(order_id, product_id)
);
CREATE TABLE IF NOT EXISTS promotions (
    promotion_id INTEGER PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(product_id),
    discount_percent TEXT NOT NULL,
    description TEXT NOT NULL,
    is_active INTEGER NOT NULL CHECK (is_active IN (0,1))
);
CREATE TABLE IF NOT EXISTS policies (
    section_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    source_page INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_products_category ON products(category_id);
CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders(customer_id);
CREATE INDEX IF NOT EXISTS idx_promotions_product ON promotions(product_id);
"""

FIELDS = {
    "categories": ("category_id", "name", "description"),
    "products": ("product_id", "price_brl", "name", "category_id", "description", "stock_quantity", "status", "specs", "created_at"),
    "customers": ("customer_id", "name", "phone", "email", "city"),
    "orders": ("order_id", "customer_id", "order_date", "status", "total_brl", "payment_method", "tracking_code", "estimated_delivery", "notes"),
    "order_items": ("order_id", "quantity", "product_id"),
    "promotions": ("promotion_id", "product_id", "discount_percent", "description", "is_active"),
}
LOAD_ORDER = ("categories", "products", "customers", "orders", "order_items", "promotions")
INT_FIELDS = {"category_id", "product_id", "customer_id", "order_id", "quantity", "stock_quantity", "promotion_id", "is_active"}
DEC_FIELDS = {"price_brl", "total_brl", "discount_percent"}


def read_only_connection(db_path: str | Path) -> sqlite3.Connection:
    path = Path(db_path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Database not found: {path}. Run scripts/prepare_data.py first.")
    connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only=ON")
    return connection


def _read_csv(path: Path, expected: tuple[str, ...]) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames is None or tuple(reader.fieldnames) != expected:
            raise ValueError(f"Unexpected columns in {path.name}: {reader.fieldnames}")
        output = []
        for line, row in enumerate(reader, start=2):
            cleaned = {}
            for key in expected:
                value = row[key]
                if value is None:
                    raise ValueError(f"Missing value: {path}:{line}:{key}")
                if key in INT_FIELDS:
                    cleaned[key] = int(value)
                elif key in DEC_FIELDS:
                    try:
                        decimal = Decimal(value)
                        if not decimal.is_finite() or decimal < 0:
                            raise ValueError("non-finite or negative number")
                    except (InvalidOperation, ValueError) as exc:
                        raise ValueError(f"Invalid amount: {path}:{line}:{key}") from exc
                    cleaned[key] = str(decimal)
                else:
                    cleaned[key] = value.strip()
            if "specs" in cleaned:
                json.loads(cleaned["specs"])
            output.append(cleaned)
        return output


def _find_csv(folder: Path, name: str) -> Path:
    matches = sorted(folder.rglob(f"* - {name}.csv"))
    matches += sorted(folder.rglob(f"{name}.csv"))
    matches = list(dict.fromkeys(matches))
    if len(matches) != 1:
        raise FileNotFoundError(f"Expected exactly one {name}.csv in {folder}; found {len(matches)}")
    return matches[0]


def build_database(db_path: str | Path, source_dir: str | Path, sections: list[dict]) -> dict[str, int]:
    """Create DB atomically; never replace an existing DB on import failure."""
    source_dir, db_path = Path(source_dir), Path(db_path)
    rows = {name: _read_csv(_find_csv(source_dir, name), FIELDS[name]) for name in LOAD_ORDER}
    db_path.parent.mkdir(parents=True, exist_ok=True)
    temp = db_path.with_name(db_path.name + ".building")
    temp.unlink(missing_ok=True)
    try:
        with sqlite3.connect(temp) as conn:
            conn.executescript(SCHEMA)
            for name in LOAD_ORDER:
                columns = FIELDS[name]
                placeholders = ",".join("?" for _ in columns)
                conn.executemany(
                    f"INSERT INTO {name} ({','.join(columns)}) VALUES ({placeholders})",
                    ([row[field] for field in columns] for row in rows[name]),
                )
            conn.executemany(
                "INSERT INTO policies (section_id,title,content,source_page) VALUES (?,?,?,?)",
                ((p["section_id"], p["title"], p["content"], int(p["source_page"])) for p in sections),
            )
            if not sections:
                raise ValueError("No policies were loaded")
            foreign_key_errors = conn.execute("PRAGMA foreign_key_check").fetchall()
            if foreign_key_errors:
                raise ValueError(f"Invalid relationships: {foreign_key_errors}")
        temp.replace(db_path)
    finally:
        temp.unlink(missing_ok=True)
    return {**{key: len(value) for key, value in rows.items()}, "policies": len(sections)}
