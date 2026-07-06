# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import sqlite3
import threading

DEFAULT_DB_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "data", "nova.db"
)
db_lock = threading.RLock()


def get_db_file() -> str:
    """Returns the configured database file path."""
    return os.environ.get("NOVA_DB_FILE", DEFAULT_DB_FILE)


def init_db():
    """Initializes the SQLite database and creates the tables if they don't exist."""
    db_file = get_db_file()
    db_dir = os.path.dirname(db_file)
    if not os.path.exists(db_dir):
        os.makedirs(db_dir)

    with db_lock:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()

        def ensure_column(table: str, column: str, definition: str) -> None:
            cursor.execute(f"PRAGMA table_info({table})")
            existing = {row[1] for row in cursor.fetchall()}
            if column not in existing:
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

        # Goals table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS goals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                category TEXT,
                status TEXT NOT NULL DEFAULT 'ongoing',
                target_date TEXT
            )
        """)

        # Tasks table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                category TEXT NOT NULL DEFAULT 'Personal',
                status TEXT NOT NULL DEFAULT 'pending',
                priority TEXT NOT NULL DEFAULT 'medium',
                due_date TEXT,
                scheduled_time TEXT,
                duration INTEGER,
                completed_at TEXT,
                goal_id INTEGER,
                FOREIGN KEY(goal_id) REFERENCES goals(id) ON DELETE SET NULL
            )
        """)

        # Reminders table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL,
                reminder_time TEXT NOT NULL,
                message TEXT,
                delivery_type TEXT NOT NULL DEFAULT 'task',
                status TEXT NOT NULL DEFAULT 'pending',
                is_sent INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
            )
        """)
        ensure_column("reminders", "message", "TEXT")
        ensure_column("reminders", "delivery_type", "TEXT NOT NULL DEFAULT 'task'")
        ensure_column("reminders", "status", "TEXT NOT NULL DEFAULT 'pending'")

        # Preferences table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS preferences (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)

        # Productivity logs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS productivity_logs (
                date TEXT PRIMARY KEY,
                log_data TEXT NOT NULL
            )
        """)

        # Notifications table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_type TEXT NOT NULL,
                source_id INTEGER,
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                severity TEXT NOT NULL DEFAULT 'info',
                scheduled_for TEXT,
                delivered_at TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                metadata TEXT
            )
        """)

        # Habits table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS habits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                category TEXT NOT NULL DEFAULT 'Personal',
                frequency TEXT NOT NULL DEFAULT 'daily',
                target_count INTEGER NOT NULL DEFAULT 1,
                status TEXT NOT NULL DEFAULT 'active',
                start_date TEXT,
                reminder_time TEXT,
                goal_id INTEGER,
                streak_current INTEGER NOT NULL DEFAULT 0,
                streak_best INTEGER NOT NULL DEFAULT 0,
                last_completed_date TEXT,
                FOREIGN KEY(goal_id) REFERENCES goals(id) ON DELETE SET NULL
            )
        """)

        # Habit logs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS habit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                habit_id INTEGER NOT NULL,
                log_date TEXT NOT NULL,
                completed_count INTEGER NOT NULL DEFAULT 1,
                notes TEXT,
                FOREIGN KEY(habit_id) REFERENCES habits(id) ON DELETE CASCADE
            )
        """)

        # Long-term memory table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS memory_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                memory_type TEXT NOT NULL DEFAULT 'preference',
                content TEXT NOT NULL,
                tags TEXT,
                related_goal_id INTEGER,
                related_task_id INTEGER,
                importance INTEGER NOT NULL DEFAULT 3,
                created_at TEXT NOT NULL,
                last_recalled_at TEXT,
                FOREIGN KEY(related_goal_id) REFERENCES goals(id) ON DELETE SET NULL,
                FOREIGN KEY(related_task_id) REFERENCES tasks(id) ON DELETE SET NULL
            )
        """)

        # User-defined categories table (replaces hard-coded category lists)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            )
        """)

        conn.commit()
        conn.close()


def get_db_connection():
    """Returns a connection to the SQLite database. Callers must close it."""
    db_file = get_db_file()
    # Always run initialization so new tables/columns are migrated into existing DBs.
    init_db()
    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    return conn
