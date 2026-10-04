"""Build ventes.db, the SQLite source for the Ain Token dashboard.

    python create_db.py           # the 10-row dataset from the specification
    python create_db.py --rich    # deterministic 12-month demo dataset

Re-running is safe: the database file is deleted and rebuilt from scratch.
"""

from __future__ import annotations

import argparse
import random
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "ventes.db"

SCHEMA = """
CREATE TABLE customers (
    customer_id INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    region      TEXT NOT NULL,
    segment     TEXT NOT NULL            -- 'Developer', 'Startup' or 'Enterprise'
);

CREATE TABLE products (
    product_id  INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    category    TEXT NOT NULL,
    unit_price  REAL NOT NULL            -- DA per 1 million tokens
);

CREATE TABLE sales (
    sale_id     INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(customer_id),
    product_id  INTEGER NOT NULL REFERENCES products(product_id),
    quantity    INTEGER NOT NULL,        -- millions of tokens
    sale_date   TEXT NOT NULL            -- format YYYY-MM-DD
);
"""

# API clients spread over the Algerian regions.
CUSTOMERS = [
    (1, "Nova Code Studio", "Alger", "Startup"),
    (2, "Oran Data Labs", "Oran", "Startup"),
    (3, "Cirta Analytics", "Constantine", "Enterprise"),
    (4, "Soummam Dev Team", "Béjaïa", "Developer"),
    (5, "Aurès Software House", "Batna", "Enterprise"),
]

# Models hosted on Ain Token's GPUs. unit_price = DA per 1 million tokens.
PRODUCTS = [
    (1, "Qwen3 30B-A3B", "General chat", 120),
    (2, "Qwen3 32B", "Quality chat", 280),
    (3, "Qwen2.5-Coder 32B", "Coding", 260),
    (4, "Llama 3.1 8B", "Small and fast", 45),
    (5, "gpt-oss-20b", "Reasoning", 150),
]

# Token purchases / invoices: quantity is in millions of tokens.
SALES = [
    (1, 1, 1, 400, "2026-01-12"),
    (2, 2, 3, 250, "2026-01-25"),
    (3, 3, 2, 600, "2026-02-08"),
    (4, 4, 4, 1200, "2026-02-19"),
    (5, 1, 5, 300, "2026-03-03"),
    (6, 5, 1, 900, "2026-03-17"),
    (7, 2, 3, 500, "2026-04-05"),
    (8, 3, 1, 1500, "2026-04-22"),
    (9, 4, 2, 350, "2026-05-14"),
    (10, 5, 5, 800, "2026-06-09"),
]

_QUANTITIES = [100, 150, 200, 250, 300, 400, 500, 600, 750, 900, 1200]


def demo_sales(seed: int = 42) -> list[tuple]:
    """Deterministic 12-month dataset (Jan-Dec 2026) for a fuller-looking demo."""
    rng = random.Random(seed)
    rows, sale_id = [], 0
    for month in range(1, 13):
        for customer_id in range(1, 6):
            for _ in range(rng.randint(1, 3)):
                sale_id += 1
                rows.append((
                    sale_id,
                    customer_id,
                    rng.randint(1, 5),
                    rng.choice(_QUANTITIES),
                    f"2026-{month:02d}-{rng.randint(1, 28):02d}",
                ))
    return rows


def build(db_path: Path | str = DB_PATH, rich: bool = False) -> Path:
    """(Re)create the database at db_path and return the path."""
    db_path = Path(db_path)
    db_path.unlink(missing_ok=True)
    sales = demo_sales() if rich else SALES

    con = sqlite3.connect(db_path)
    try:
        con.executescript(SCHEMA)
        con.executemany("INSERT INTO customers VALUES (?, ?, ?, ?)", CUSTOMERS)
        con.executemany("INSERT INTO products VALUES (?, ?, ?, ?)", PRODUCTS)
        con.executemany("INSERT INTO sales VALUES (?, ?, ?, ?, ?)", sales)
        con.commit()
    finally:
        con.close()
    return db_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rich", action="store_true",
                        help="use the generated 12-month dataset instead of the 10-row spec dataset")
    args = parser.parse_args()

    path = build(rich=args.rich)
    con = sqlite3.connect(path)
    try:
        counts = {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                  for t in ("customers", "products", "sales")}
    finally:
        con.close()

    print(f"Database rebuilt: {path}")
    for table, n in counts.items():
        print(f"  {table:<10} {n} rows")


if __name__ == "__main__":
    main()
