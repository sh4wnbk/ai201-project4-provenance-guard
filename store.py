"""Audit log (INSERT-only) and status store — SQLite backend."""
import json
import sqlite3


class Store:
    def __init__(self, path: str) -> None:
        self.path = path
        with self._connect() as con:
            con.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id        INTEGER PRIMARY KEY AUTOINCREMENT,
                    content_id TEXT NOT NULL,
                    entry_type TEXT NOT NULL,
                    data      TEXT NOT NULL,
                    timestamp TEXT NOT NULL
                )
            """)
            con.execute("""
                CREATE TABLE IF NOT EXISTS status_store (
                    content_id TEXT PRIMARY KEY,
                    status     TEXT NOT NULL
                )
            """)
            con.execute("""
                CREATE TABLE IF NOT EXISTS creator_status (
                    creator_id TEXT PRIMARY KEY,
                    status     TEXT NOT NULL
                )
            """)

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.path)
        con.row_factory = sqlite3.Row
        return con

    # --- Audit log (INSERT-only) ---

    def append_log(self, entry: dict) -> None:
        """Insert an entry into the audit log. Never updates or deletes."""
        with self._connect() as con:
            con.execute(
                "INSERT INTO audit_log (content_id, entry_type, data, timestamp) VALUES (?,?,?,?)",
                (
                    entry["content_id"],
                    entry.get("entry_type", "classification"),
                    json.dumps(entry),
                    entry["timestamp"],
                ),
            )

    def get_log(self, limit: int = 50) -> list[dict]:
        """Return the most recent entries, newest first."""
        with self._connect() as con:
            rows = con.execute(
                "SELECT data FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [json.loads(r["data"]) for r in rows]

    def get_log_entry(self, content_id: str) -> dict | None:
        """Return the first classification entry for content_id, or None."""
        with self._connect() as con:
            row = con.execute(
                "SELECT data FROM audit_log WHERE content_id=? AND entry_type='classification' LIMIT 1",
                (content_id,),
            ).fetchone()
        return json.loads(row["data"]) if row else None

    # --- Status store (mutable) ---

    def set_status(self, content_id: str, status: str) -> None:
        with self._connect() as con:
            con.execute(
                "INSERT INTO status_store (content_id, status) VALUES (?,?) "
                "ON CONFLICT(content_id) DO UPDATE SET status=excluded.status",
                (content_id, status),
            )

    def get_status(self, content_id: str) -> str | None:
        with self._connect() as con:
            row = con.execute(
                "SELECT status FROM status_store WHERE content_id=?", (content_id,)
            ).fetchone()
        return row["status"] if row else None

    def known_content_id(self, content_id: str) -> bool:
        return self.get_status(content_id) is not None

    # --- Creator verification status ---

    def set_creator_status(self, creator_id: str, status: str) -> None:
        with self._connect() as con:
            con.execute(
                "INSERT INTO creator_status (creator_id, status) VALUES (?,?) "
                "ON CONFLICT(creator_id) DO UPDATE SET status=excluded.status",
                (creator_id, status),
            )

    def get_creator_status(self, creator_id: str) -> str:
        with self._connect() as con:
            row = con.execute(
                "SELECT status FROM creator_status WHERE creator_id=?", (creator_id,)
            ).fetchone()
        return row["status"] if row else "unverified"
