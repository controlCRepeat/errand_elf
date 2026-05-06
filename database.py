import time
import psycopg2
import psycopg2.extras
from config import DATABASE_URL


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------

def get_conn():
    return psycopg2.connect(DATABASE_URL)


def init_db():
    """Create tables on startup. Retries with exponential backoff."""
    for attempt in range(5):
        try:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS fridge_current (
                            item_name   TEXT PRIMARY KEY,
                            expiry      DATE NOT NULL,
                            qty         INT  NOT NULL DEFAULT 0,
                            category    TEXT NOT NULL,
                            updated_at  TIMESTAMPTZ DEFAULT NOW()
                        )
                    """)
                conn.commit()
            print("DB ready ✅")
            return
        except Exception as e:
            wait = 2 ** attempt
            print(f"DB connection failed (attempt {attempt + 1}): {e}")
            time.sleep(wait)
    raise RuntimeError("Could not connect to DB after 5 attempts")


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------

def upsert_item(item_name: str, expiry, qty: int, category: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO fridge_current (item_name, expiry, qty, category, updated_at)
                VALUES (%s, %s, %s, %s, NOW())
                ON CONFLICT (item_name) DO UPDATE
                SET expiry     = EXCLUDED.expiry,
                    qty        = EXCLUDED.qty,
                    category   = EXCLUDED.category,
                    updated_at = NOW()
            """, (item_name, expiry, qty, category))
        conn.commit()


def soft_delete_item(item_name: str):
    """Set qty to 0 instead of deleting the row."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE fridge_current
                SET qty = 0, updated_at = NOW()
                WHERE item_name = %s
            """, (item_name,))
        conn.commit()


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------

def get_item(item_name: str):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM fridge_current WHERE item_name = %s", (item_name,))
            return cur.fetchone()


def get_all_items():
    """Returns only in-stock items (qty > 0), ordered by category then expiry."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT * FROM fridge_current
                WHERE qty > 0
                ORDER BY category ASC, expiry ASC
            """)
            return cur.fetchall()