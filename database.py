"""
database.py - ניהול מסד נתונים SQLite לסוכן הוואטסאפ
"""
import sqlite3
import json
import os

DB_PATH = os.getenv("DB_PATH", "social_agent.db")

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            tone TEXT DEFAULT 'מקצועי ונחמד',
            target_audience TEXT DEFAULT 'כללי',
            forbidden_topics TEXT DEFAULT '[]',
            preferred_posting_days TEXT DEFAULT '["ראשון", "שלישי", "חמישי"]',
            extra_info TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone_number TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.commit()
    conn.close()

def add_client(name, tone="מקצועי ונחמד", target_audience="כללי",
               forbidden_topics=None, preferred_posting_days=None, extra_info=""):
    if forbidden_topics is None:
        forbidden_topics = []
    if preferred_posting_days is None:
        preferred_posting_days = ["ראשון", "שלישי", "חמישי"]
    conn = get_connection()
    try:
        conn.execute("""
            INSERT INTO clients (name, tone, target_audience, forbidden_topics, preferred_posting_days, extra_info)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (name, tone, target_audience,
              json.dumps(forbidden_topics, ensure_ascii=False),
              json.dumps(preferred_posting_days, ensure_ascii=False),
              extra_info))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def get_client(name):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM clients WHERE name = ?", (name,))
    row = cursor.fetchone()
    conn.close()
    return _row_to_dict(row) if row else None

def get_all_clients():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM clients ORDER BY name")
    rows = cursor.fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]

def _row_to_dict(row):
    d = dict(row)
    for field in ["forbidden_topics", "preferred_posting_days"]:
        if field in d and isinstance(d[field], str):
            try:
                d[field] = json.loads(d[field])
            except:
                d[field] = []
    return d

def save_message(phone_number, role, content):
    conn = get_connection()
    conn.execute("INSERT INTO conversations (phone_number, role, content) VALUES (?, ?, ?)",
                 (phone_number, role, content))
    conn.commit()
    conn.close()

def get_conversation_history(phone_number, limit=20):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT role, content FROM conversations
        WHERE phone_number = ?
        ORDER BY timestamp DESC LIMIT ?
    """, (phone_number, limit))
    rows = cursor.fetchall()
    conn.close()
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]

def clear_conversation_history(phone_number):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM conversations WHERE phone_number = ?", (phone_number,))
    conn.commit()
    affected = cursor.rowcount
    conn.close()
    return affected
