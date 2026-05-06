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
                            qty         INT  NOT NULL,
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


def delete_item(item_name: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM fridge_current WHERE item_name = %s", (item_name,))
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
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM fridge_current ORDER BY expiry ASC")
            return cur.fetchall()
