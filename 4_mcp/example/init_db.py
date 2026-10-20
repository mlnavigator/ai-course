"""Создать учебную БД. Повторное создание: python init_db.py --reset."""
import argparse
import sqlite3
from contextlib import closing
from pathlib import Path

DB = Path(__file__).resolve().parent / "shop.db"

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE customers (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    city TEXT NOT NULL
);
CREATE TABLE products (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    price_kopecks INTEGER NOT NULL CHECK(price_kopecks >= 0),
    stock INTEGER NOT NULL CHECK(stock >= 0)
);
CREATE TABLE orders (
    id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    created_at TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('paid', 'pending', 'cancelled', 'refunded'))
);
CREATE TABLE order_items (
    order_id INTEGER NOT NULL REFERENCES orders(id),
    product_id INTEGER NOT NULL REFERENCES products(id),
    qty INTEGER NOT NULL CHECK(qty > 0),
    unit_price_kopecks INTEGER NOT NULL CHECK(unit_price_kopecks >= 0),
    PRIMARY KEY(order_id, product_id)
);
"""

CUSTOMERS = [(1, "Анна", "Кострома"), (2, "Борис", "Ярославль"),
             (3, "Вера", "Кострома"), (4, "Глеб", "Иваново")]
PRODUCTS = [(1, "Keyboard", 200000, 8), (2, "Mouse", 80000, 15),
            (3, "USB-C Cable", 40000, 0), (4, "Monitor", 1500000, 3)]
ORDERS = [(101, 1, "2026-10-01", "paid"), (102, 2, "2026-10-02", "paid"),
          (103, 1, "2026-10-03", "cancelled"), (104, 3, "2026-10-04", "paid"),
          (105, 2, "2026-10-05", "pending"), (106, 3, "2026-10-06", "refunded"),
          (107, 1, "2026-10-07", "paid")]
ITEMS = [(101, 1, 1, 200000), (101, 2, 2, 80000), (102, 4, 1, 1500000),
         (103, 3, 1, 40000), (104, 3, 3, 35000), (104, 2, 1, 80000),
         (105, 1, 1, 200000), (106, 4, 1, 1500000), (107, 2, 1, 75000)]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()
    if DB.exists():
        if not args.reset:
            raise SystemExit("БД уже существует. Для сброса используйте --reset.")
        DB.unlink()
    with closing(sqlite3.connect(DB)) as conn:
        conn.executescript(SCHEMA)
        conn.executemany("INSERT INTO customers VALUES (?, ?, ?)", CUSTOMERS)
        conn.executemany("INSERT INTO products VALUES (?, ?, ?, ?)", PRODUCTS)
        conn.executemany("INSERT INTO orders VALUES (?, ?, ?, ?)", ORDERS)
        conn.executemany("INSERT INTO order_items VALUES (?, ?, ?, ?)", ITEMS)
        conn.commit()
    print(f"Создана {DB}")


if __name__ == "__main__":
    main()
