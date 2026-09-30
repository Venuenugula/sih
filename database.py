"""SQLite helpers for users, investigations, audit log, and review."""

from __future__ import annotations

import hashlib
import secrets
import sqlite3
from datetime import datetime, timezone

from config import (
    DEMO_ADMIN_PASSWORD,
    DEMO_ADMIN_USERNAME,
    DEMO_ENGINEER_PASSWORD,
    DEMO_ENGINEER_USERNAME,
    DEMO_REVIEWER_PASSWORD,
    DEMO_REVIEWER_USERNAME,
    SQLITE_PATH,
    ensure_folders,
)


def _connect() -> sqlite3.Connection:
    ensure_folders()
    SQLITE_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def hash_password(password: str) -> str:
    """PBKDF2-SHA256 password hash. Stdlib only — no JWT."""
    salt = secrets.token_hex(16)
    rounds = 100_000
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        rounds,
    ).hex()
    return f"pbkdf2_sha256${rounds}${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _algo, rounds_s, salt, digest = stored.split("$", 3)
        check = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            int(rounds_s),
        ).hex()
        return secrets.compare_digest(check, digest)
    except Exception:
        return False


def init_db() -> None:
    conn = _connect()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL,
            department TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            username TEXT NOT NULL,
            department TEXT NOT NULL,
            action TEXT NOT NULL,
            detail TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS investigations (
            machine_id TEXT PRIMARY KEY,
            notes TEXT NOT NULL DEFAULT '',
            question TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'Open',
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            machine_id TEXT NOT NULL,
            question TEXT NOT NULL DEFAULT '',
            answer TEXT NOT NULL DEFAULT '',
            requested_by TEXT NOT NULL,
            reviewer TEXT NOT NULL DEFAULT '',
            decision TEXT NOT NULL DEFAULT 'pending',
            reason TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            decided_at TEXT NOT NULL DEFAULT ''
        );
        """
    )
    _ensure_review_columns(conn)
    conn.commit()
    conn.close()
    seed_demo_users()


def _ensure_review_columns(conn: sqlite3.Connection) -> None:
    """Add Phase 10 columns on older SQLite files."""
    cols = {row[1] for row in conn.execute("PRAGMA table_info(reviews)").fetchall()}
    if "question" not in cols:
        conn.execute("ALTER TABLE reviews ADD COLUMN question TEXT NOT NULL DEFAULT ''")
    if "answer" not in cols:
        conn.execute("ALTER TABLE reviews ADD COLUMN answer TEXT NOT NULL DEFAULT ''")


def seed_demo_users() -> None:
    """Insert demo users if missing. Does not overwrite existing password hashes."""
    seeds = [
        (DEMO_ADMIN_USERNAME, DEMO_ADMIN_PASSWORD, "Admin", "Maintenance"),
        (DEMO_ENGINEER_USERNAME, DEMO_ENGINEER_PASSWORD, "Engineer", "Maintenance"),
        (DEMO_REVIEWER_USERNAME, DEMO_REVIEWER_PASSWORD, "Reviewer", "Maintenance"),
    ]
    conn = _connect()
    for username, password, role, department in seeds:
        row = conn.execute(
            "SELECT username FROM users WHERE username = ?",
            (username,),
        ).fetchone()
        if row:
            continue
        conn.execute(
            """
            INSERT INTO users (username, password_hash, role, department)
            VALUES (?, ?, ?, ?)
            """,
            (username, hash_password(password), role, department),
        )
    conn.commit()
    conn.close()


def get_user(username: str) -> sqlite3.Row | None:
    conn = _connect()
    row = conn.execute(
        "SELECT username, password_hash, role, department FROM users WHERE username = ?",
        (username.strip(),),
    ).fetchone()
    conn.close()
    return row


def authenticate_user(username: str, password: str) -> dict | None:
    """Verify username + password against SQLite. Returns public user fields only."""
    row = get_user(username)
    if not row:
        return None
    if not verify_password(password, row["password_hash"]):
        return None
    return {
        "username": row["username"],
        "role": row["role"],
        "department": row["department"],
        "name": row["username"],
    }


def list_users() -> list[sqlite3.Row]:
    conn = _connect()
    rows = conn.execute(
        "SELECT username, role, department FROM users ORDER BY username"
    ).fetchall()
    conn.close()
    return rows


# Standard Phase 9 audit actions
AUDIT_LOGIN = "login"
AUDIT_UPLOAD = "upload"
AUDIT_DOCUMENT_SEARCH = "document search"
AUDIT_SENSOR_ANALYSIS = "sensor analysis"
AUDIT_IMAGE_ANALYSIS = "image analysis"
AUDIT_AI_QUERY = "AI query"
AUDIT_REPORT = "report generation"
AUDIT_REVIEW = "review"

AUDIT_ACTIONS = (
    AUDIT_LOGIN,
    AUDIT_UPLOAD,
    AUDIT_DOCUMENT_SEARCH,
    AUDIT_SENSOR_ANALYSIS,
    AUDIT_IMAGE_ANALYSIS,
    AUDIT_AI_QUERY,
    AUDIT_REPORT,
    AUDIT_REVIEW,
)


def log_action(username: str, department: str, action: str, detail: str) -> None:
    """Append one audit event. Passwords and API keys must never appear in detail."""
    conn = _connect()
    conn.execute(
        """
        INSERT INTO audit_log (timestamp, username, department, action, detail)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            username,
            department,
            action,
            detail,
        ),
    )
    conn.commit()
    conn.close()


def fetch_audit(limit: int = 100, action: str | None = None) -> list[sqlite3.Row]:
    conn = _connect()
    if action:
        rows = conn.execute(
            """
            SELECT timestamp, username, action, detail, department
            FROM audit_log
            WHERE action = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (action, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT timestamp, username, action, detail, department
            FROM audit_log
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    conn.close()
    return rows


def audit_table(limit: int = 200, action: str | None = None) -> list[dict]:
    """Rows shaped for the Audit Log page: timestamp, user, action, details."""
    rows = []
    for row in fetch_audit(limit=limit, action=action):
        rows.append(
            {
                "timestamp": row["timestamp"],
                "user": row["username"],
                "action": row["action"],
                "details": row["detail"],
            }
        )
    return rows


def save_investigation(machine_id: str, notes: str, question: str, status: str) -> None:
    conn = _connect()
    conn.execute(
        """
        INSERT INTO investigations (machine_id, notes, question, status, updated_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(machine_id) DO UPDATE SET
            notes = excluded.notes,
            question = excluded.question,
            status = excluded.status,
            updated_at = excluded.updated_at
        """,
        (
            machine_id,
            notes,
            question,
            status,
            datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        ),
    )
    conn.commit()
    conn.close()


def get_investigation(machine_id: str) -> sqlite3.Row | None:
    conn = _connect()
    row = conn.execute(
        "SELECT * FROM investigations WHERE machine_id = ?",
        (machine_id,),
    ).fetchone()
    conn.close()
    return row


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def submit_review(
    machine_id: str,
    requested_by: str,
    question: str = "",
    answer: str = "",
) -> int:
    """Store a human-review request: investigation, question, answer, user, timestamp, status."""
    conn = _connect()
    cur = conn.execute(
        """
        INSERT INTO reviews (
            machine_id, question, answer, requested_by, decision, created_at
        )
        VALUES (?, ?, ?, ?, 'pending', ?)
        """,
        (machine_id, question, answer, requested_by, _now()),
    )
    review_id = int(cur.lastrowid)
    conn.execute(
        "UPDATE investigations SET status = ?, updated_at = ? WHERE machine_id = ?",
        ("In review", _now(), machine_id),
    )
    conn.commit()
    conn.close()
    return review_id


def decide_review(review_id: int, reviewer: str, decision: str, reason: str = "") -> None:
    """Reviewer APPROVE or REJECT. Status becomes approved or rejected."""
    choice = "approved" if decision.lower() in {"approved", "approve"} else "rejected"
    conn = _connect()
    conn.execute(
        """
        UPDATE reviews
        SET reviewer = ?, decision = ?, reason = ?, decided_at = ?
        WHERE id = ?
        """,
        (reviewer, choice, reason or "", _now(), review_id),
    )
    row = conn.execute("SELECT machine_id FROM reviews WHERE id = ?", (review_id,)).fetchone()
    if row:
        inv_status = "Closed" if choice == "approved" else "Open"
        conn.execute(
            "UPDATE investigations SET status = ?, updated_at = ? WHERE machine_id = ?",
            (inv_status, _now(), row["machine_id"]),
        )
    conn.commit()
    conn.close()


def latest_review(machine_id: str) -> sqlite3.Row | None:
    conn = _connect()
    row = conn.execute(
        """
        SELECT * FROM reviews
        WHERE machine_id = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (machine_id,),
    ).fetchone()
    conn.close()
    return row


def review_as_dict(row: sqlite3.Row | None) -> dict | None:
    """Shape a review row for UI/PDF: investigation, question, answer, user, timestamp, status."""
    if row is None:
        return None
    return {
        "id": row["id"],
        "investigation": row["machine_id"],
        "question": row["question"] if "question" in row.keys() else "",
        "answer": row["answer"] if "answer" in row.keys() else "",
        "user": row["requested_by"],
        "timestamp": row["created_at"],
        "status": row["decision"],
        "reviewer": row["reviewer"],
        "reason": row["reason"],
        "decided_at": row["decided_at"],
        # keep legacy keys used by report.py
        "machine_id": row["machine_id"],
        "requested_by": row["requested_by"],
        "decision": row["decision"],
        "created_at": row["created_at"],
    }


def list_reviews(limit: int = 50, status: str | None = None) -> list[sqlite3.Row]:
    conn = _connect()
    if status:
        rows = conn.execute(
            "SELECT * FROM reviews WHERE decision = ? ORDER BY id DESC LIMIT ?",
            (status, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM reviews ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    conn.close()
    return rows
