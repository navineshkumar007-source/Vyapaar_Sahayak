"""
SQLite database layer for Vyapaar Sahayak.

Design notes:
- This prototype is built for a single active business profile at a time
  (matching a single-shop-owner demo flow), but the schema is normalised
  into proper tables so it can grow into a multi-profile app later.
- All functions are defensive: missing DB / tables are created on demand,
  and reads return sensible empty defaults instead of raising.
"""

import sqlite3
import json
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).resolve().parent.parent / "vyapaar_sahayak.db"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


@contextmanager
def get_connection():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    try:
        yield con
        con.commit()
    finally:
        con.close()


def init_db() -> None:
    """Create all tables if they do not already exist. Safe to call every run."""
    with get_connection() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS business_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                business_type TEXT NOT NULL,
                location TEXT,
                state TEXT,
                district TEXT,
                language TEXT DEFAULT 'English',
                employees INTEGER DEFAULT 0,
                season TEXT DEFAULT 'Regular',
                local_event TEXT DEFAULT '',
                is_demo INTEGER DEFAULT 0,
                created_at TEXT,
                updated_at TEXT
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS financial_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_id INTEGER NOT NULL,
                revenue REAL DEFAULT 0,
                expenses REAL DEFAULT 0,
                inventory_value REAL DEFAULT 0,
                receivables REAL DEFAULT 0,
                cash REAL DEFAULT 0,
                loan_outstanding REAL DEFAULT 0,
                loan_emi REAL DEFAULT 0,
                created_at TEXT,
                FOREIGN KEY (profile_id) REFERENCES business_profiles (id)
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS inventory_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_id INTEGER NOT NULL,
                product_name TEXT NOT NULL,
                category TEXT,
                quantity REAL DEFAULT 0,
                purchase_price REAL DEFAULT 0,
                selling_price REAL DEFAULT 0,
                monthly_units_sold REAL DEFAULT 0,
                history_json TEXT DEFAULT '[]',
                created_at TEXT,
                updated_at TEXT,
                FOREIGN KEY (profile_id) REFERENCES business_profiles (id)
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS action_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                reason TEXT,
                expected_impact TEXT,
                priority TEXT DEFAULT 'Medium',
                timeframe TEXT DEFAULT 'This Week',
                status TEXT DEFAULT 'Not Started',
                created_at TEXT,
                updated_at TEXT,
                FOREIGN KEY (profile_id) REFERENCES business_profiles (id)
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS chat_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TEXT,
                FOREIGN KEY (profile_id) REFERENCES business_profiles (id)
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS scheme_bookmarks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_id INTEGER NOT NULL,
                scheme_name TEXT NOT NULL,
                created_at TEXT,
                FOREIGN KEY (profile_id) REFERENCES business_profiles (id)
            )
        """)


# ---------------------------------------------------------------------------
# Business profile
# ---------------------------------------------------------------------------

def get_active_profile():
    """Return the most recently updated business profile, or None."""
    with get_connection() as con:
        row = con.execute(
            "SELECT * FROM business_profiles ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None


def upsert_profile(profile: dict, profile_id: Optional[int] = None) -> int:
    """Create a new profile, or update an existing one if profile_id is given."""
    with get_connection() as con:
        if profile_id:
            con.execute("""
                UPDATE business_profiles
                SET name=?, business_type=?, location=?, state=?, district=?,
                    language=?, employees=?, season=?, local_event=?, updated_at=?
                WHERE id=?
            """, (
                profile["name"], profile["business_type"], profile.get("location", ""),
                profile.get("state", ""), profile.get("district", ""),
                profile.get("language", "English"), profile.get("employees", 0),
                profile.get("season", "Regular"), profile.get("local_event", ""),
                _now(), profile_id
            ))
            return profile_id
        cur = con.execute("""
            INSERT INTO business_profiles
                (name, business_type, location, state, district, language,
                 employees, season, local_event, is_demo, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            profile["name"], profile["business_type"], profile.get("location", ""),
            profile.get("state", ""), profile.get("district", ""),
            profile.get("language", "English"), profile.get("employees", 0),
            profile.get("season", "Regular"), profile.get("local_event", ""),
            int(profile.get("is_demo", 0)), _now(), _now()
        ))
        return cur.lastrowid


# ---------------------------------------------------------------------------
# Financial snapshots
# ---------------------------------------------------------------------------

def add_snapshot(profile_id: int, snapshot: dict) -> int:
    with get_connection() as con:
        cur = con.execute("""
            INSERT INTO financial_snapshots
                (profile_id, revenue, expenses, inventory_value, receivables,
                 cash, loan_outstanding, loan_emi, created_at)
            VALUES (?,?,?,?,?,?,?,?,?)
        """, (
            profile_id, snapshot.get("revenue", 0), snapshot.get("expenses", 0),
            snapshot.get("inventory_value", 0), snapshot.get("receivables", 0),
            snapshot.get("cash", 0), snapshot.get("loan_outstanding", 0),
            snapshot.get("loan_emi", 0), _now()
        ))
        return cur.lastrowid


def get_latest_snapshots(profile_id: int, limit: int = 2):
    """Return up to `limit` most recent snapshots, newest first, as dicts."""
    with get_connection() as con:
        rows = con.execute("""
            SELECT * FROM financial_snapshots
            WHERE profile_id=? ORDER BY id DESC LIMIT ?
        """, (profile_id, limit)).fetchall()
        return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Inventory
# ---------------------------------------------------------------------------

def add_inventory_item(profile_id: int, item: dict) -> int:
    with get_connection() as con:
        cur = con.execute("""
            INSERT INTO inventory_items
                (profile_id, product_name, category, quantity, purchase_price,
                 selling_price, monthly_units_sold, history_json, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (
            profile_id, item["product_name"], item.get("category", "Other"),
            item.get("quantity", 0), item.get("purchase_price", 0),
            item.get("selling_price", 0), item.get("monthly_units_sold", 0),
            json.dumps(item.get("history", [])), _now(), _now()
        ))
        return cur.lastrowid


def list_inventory_items(profile_id: int):
    with get_connection() as con:
        rows = con.execute(
            "SELECT * FROM inventory_items WHERE profile_id=? ORDER BY id ASC",
            (profile_id,)
        ).fetchall()
        items = []
        for r in rows:
            d = dict(r)
            try:
                d["history"] = json.loads(d.get("history_json") or "[]")
            except (json.JSONDecodeError, TypeError):
                d["history"] = []
            items.append(d)
        return items


def update_inventory_item(item_id: int, fields: dict) -> None:
    """Update one or more editable columns on an inventory item (partial update)."""
    allowed = {"product_name", "category", "quantity", "purchase_price",
               "selling_price", "monthly_units_sold"}
    to_set = {k: v for k, v in fields.items() if k in allowed}
    if not to_set:
        return
    with get_connection() as con:
        set_clause = ", ".join(f"{k}=?" for k in to_set)
        values = list(to_set.values()) + [_now(), item_id]
        con.execute(
            f"UPDATE inventory_items SET {set_clause}, updated_at=? WHERE id=?",
            values
        )


def delete_inventory_item(item_id: int) -> None:
    with get_connection() as con:
        con.execute("DELETE FROM inventory_items WHERE id=?", (item_id,))


def clear_inventory(profile_id: int) -> None:
    with get_connection() as con:
        con.execute("DELETE FROM inventory_items WHERE profile_id=?", (profile_id,))


# ---------------------------------------------------------------------------
# Action items
# ---------------------------------------------------------------------------

def replace_action_items(profile_id: int, items: list) -> None:
    """Delete all NOT-completed items and insert a fresh set (keeps completed history)."""
    with get_connection() as con:
        con.execute(
            "DELETE FROM action_items WHERE profile_id=? AND status != 'Completed'",
            (profile_id,)
        )
        for it in items:
            con.execute("""
                INSERT INTO action_items
                    (profile_id, title, reason, expected_impact, priority,
                     timeframe, status, created_at, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?)
            """, (
                profile_id, it["title"], it.get("reason", ""), it.get("expected_impact", ""),
                it.get("priority", "Medium"), it.get("timeframe", "This Week"),
                "Not Started", _now(), _now()
            ))


def list_action_items(profile_id: int):
    with get_connection() as con:
        rows = con.execute(
            "SELECT * FROM action_items WHERE profile_id=? ORDER BY id ASC",
            (profile_id,)
        ).fetchall()
        return [dict(r) for r in rows]


def update_action_status(item_id: int, status: str) -> None:
    with get_connection() as con:
        con.execute(
            "UPDATE action_items SET status=?, updated_at=? WHERE id=?",
            (status, _now(), item_id)
        )


# ---------------------------------------------------------------------------
# Chat history
# ---------------------------------------------------------------------------

def add_chat_message(profile_id: int, role: str, message: str) -> None:
    with get_connection() as con:
        con.execute(
            "INSERT INTO chat_history (profile_id, role, message, created_at) VALUES (?,?,?,?)",
            (profile_id, role, message, _now())
        )


def list_chat_history(profile_id: int, limit: int = 50):
    with get_connection() as con:
        rows = con.execute("""
            SELECT * FROM chat_history WHERE profile_id=?
            ORDER BY id ASC LIMIT ?
        """, (profile_id, limit)).fetchall()
        return [dict(r) for r in rows]


def clear_chat_history(profile_id: int) -> None:
    with get_connection() as con:
        con.execute("DELETE FROM chat_history WHERE profile_id=?", (profile_id,))


# ---------------------------------------------------------------------------
# Scheme bookmarks
# ---------------------------------------------------------------------------

def toggle_bookmark(profile_id: int, scheme_name: str) -> bool:
    """Toggle a bookmark; returns True if now bookmarked, False if removed."""
    with get_connection() as con:
        row = con.execute(
            "SELECT id FROM scheme_bookmarks WHERE profile_id=? AND scheme_name=?",
            (profile_id, scheme_name)
        ).fetchone()
        if row:
            con.execute("DELETE FROM scheme_bookmarks WHERE id=?", (row["id"],))
            return False
        con.execute(
            "INSERT INTO scheme_bookmarks (profile_id, scheme_name, created_at) VALUES (?,?,?)",
            (profile_id, scheme_name, _now())
        )
        return True


def list_bookmarks(profile_id: int):
    with get_connection() as con:
        rows = con.execute(
            "SELECT scheme_name FROM scheme_bookmarks WHERE profile_id=?",
            (profile_id,)
        ).fetchall()
        return [r["scheme_name"] for r in rows]


# ---------------------------------------------------------------------------
# Reset / wipe
# ---------------------------------------------------------------------------

def reset_all_data() -> None:
    """Wipe every table. Used by 'Reset Demo Data'."""
    with get_connection() as con:
        for table in [
            "scheme_bookmarks", "chat_history", "action_items",
            "inventory_items", "financial_snapshots", "business_profiles",
        ]:
            con.execute(f"DELETE FROM {table}")