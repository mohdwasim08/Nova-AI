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

import json
from typing import Any

from app.database import db_lock, get_db_connection


class ProductivityStore:
    """Interface defining database operations for Nova's storage.
    Ensures scalability to external systems (Google Tasks/Calendar/etc.) later.
    """

    def create_task(
        self,
        title: str,
        description: str | None = None,
        category: str = "Personal",
        priority: str = "medium",
        due_date: str | None = None,
        scheduled_time: str | None = None,
        duration: int | None = None,
        goal_id: int | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError

    def get_task(self, task_id: int) -> dict[str, Any] | None:
        raise NotImplementedError

    def update_task(self, task_id: int, **kwargs) -> dict[str, Any]:
        raise NotImplementedError

    def delete_task(self, task_id: int) -> bool:
        raise NotImplementedError

    def list_tasks(
        self, status: str | None = None, category: str | None = None
    ) -> list[dict[str, Any]]:
        raise NotImplementedError

    def create_goal(
        self,
        title: str,
        description: str | None = None,
        category: str | None = None,
        target_date: str | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError

    def get_goal(self, goal_id: int) -> dict[str, Any] | None:
        raise NotImplementedError

    def update_goal(self, goal_id: int, **kwargs) -> dict[str, Any]:
        raise NotImplementedError

    def delete_goal(self, goal_id: int) -> bool:
        raise NotImplementedError

    def list_goals(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    def set_preference(self, key: str, value: Any) -> None:
        raise NotImplementedError

    def get_preference(self, key: str, default: Any = None) -> Any:
        raise NotImplementedError

    # --- Categories ---
    def create_category(self, name: str) -> dict[str, Any]:
        raise NotImplementedError

    def list_categories(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    def rename_category(self, category_id: int, new_name: str) -> dict[str, Any] | None:
        raise NotImplementedError

    def delete_category(self, category_id: int) -> dict[str, bool | str]:
        """Deletes the category. Returns {'deleted': True} or {'deleted': False, 'reason': ...}."""
        raise NotImplementedError

    def update_task_reminder(self, task_id: int, reminder_time: str | None, title: str) -> None:
        raise NotImplementedError

    def notification_exists(self, source_type: str, source_id: int) -> bool:
        raise NotImplementedError


class SQLiteProductivityStore(ProductivityStore):
    """SQLite implementation of the ProductivityStore interface."""

    def create_task(
        self,
        title: str,
        description: str | None = None,
        category: str = "Personal",
        priority: str = "medium",
        due_date: str | None = None,
        scheduled_time: str | None = None,
        duration: int | None = None,
        goal_id: int | None = None,
    ) -> dict[str, Any]:
        with db_lock:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO tasks (title, description, category, status, priority, due_date, scheduled_time, duration, goal_id)
                   VALUES (?, ?, ?, 'pending', ?, ?, ?, ?, ?)""",
                (
                    title,
                    description,
                    category,
                    priority,
                    due_date,
                    scheduled_time,
                    duration,
                    goal_id,
                ),
            )
            task_id = cursor.lastrowid
            conn.commit()
            conn.close()
        return self.get_task(task_id)

    def get_task(self, task_id: int) -> dict[str, Any] | None:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def update_task(self, task_id: int, **kwargs) -> dict[str, Any]:
        # Filter kwargs to match column names
        valid_cols = {
            "title",
            "description",
            "category",
            "status",
            "priority",
            "due_date",
            "scheduled_time",
            "duration",
            "completed_at",
            "goal_id",
        }
        updates = {k: v for k, v in kwargs.items() if k in valid_cols}
        if not updates:
            return self.get_task(task_id)

        sql = (
            "UPDATE tasks SET "
            + ", ".join([f"{k} = ?" for k in updates.keys()])
            + " WHERE id = ?"
        )
        params = [*list(updates.values()), task_id]

        with db_lock:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(sql, params)

            # Sync status updates: Completed tasks should no longer have pending reminders or notifications
            if updates.get("status") == "completed":
                cursor.execute("DELETE FROM reminders WHERE task_id = ? AND is_sent = 0", (task_id,))
                cursor.execute("DELETE FROM notifications WHERE metadata LIKE ?", (f'%"task_id": {task_id}%',))
                cursor.execute("DELETE FROM notifications WHERE metadata LIKE ?", (f'%"task_id":{task_id}%',))
                cursor.execute("DELETE FROM notifications WHERE source_type = 'task_overdue' AND source_id = ?", (task_id,))

            # Sync title updates: Keep reminder and notification messages in sync with the new task title
            if "title" in updates:
                new_title = updates["title"]
                cursor.execute("UPDATE reminders SET message = ? WHERE task_id = ?", (f"Reminder: {new_title}", task_id))
                cursor.execute("SELECT id FROM reminders WHERE task_id = ?", (task_id,))
                reminder_ids = [row[0] for row in cursor.fetchall()]
                for r_id in reminder_ids:
                    cursor.execute(
                        "UPDATE notifications SET title = ?, message = ? WHERE source_type = 'reminder' AND source_id = ?",
                        (f"Reminder for {new_title}", f"Reminder: {new_title}", r_id)
                    )

            conn.commit()
            conn.close()
        return self.get_task(task_id)

    def delete_task(self, task_id: int) -> bool:
        with db_lock:
            conn = get_db_connection()
            cursor = conn.cursor()
            # Fetch reminder IDs for this task
            cursor.execute("SELECT id FROM reminders WHERE task_id = ?", (task_id,))
            reminder_ids = [row[0] for row in cursor.fetchall()]

            # Delete notifications associated with these reminders
            if reminder_ids:
                placeholder = ",".join("?" for _ in reminder_ids)
                cursor.execute(
                    f"DELETE FROM notifications WHERE source_type = 'reminder' AND source_id IN ({placeholder})",
                    reminder_ids,
                )

            # Delete notifications directly targeting this task_id in metadata or source_id
            cursor.execute("DELETE FROM notifications WHERE metadata LIKE ?", (f'%"task_id": {task_id}%',))
            cursor.execute("DELETE FROM notifications WHERE metadata LIKE ?", (f'%"task_id":{task_id}%',))
            cursor.execute("DELETE FROM notifications WHERE source_type = 'task_overdue' AND source_id = ?", (task_id,))

            # Delete task (SQLite CASCADE will handle reminders table deletion)
            cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            changes = conn.total_changes
            conn.commit()
            conn.close()
        return changes > 0

    def list_tasks(
        self, status: str | None = None, category: str | None = None
    ) -> list[dict[str, Any]]:
        conn = get_db_connection()
        cursor = conn.cursor()
        query = "SELECT * FROM tasks"
        params = []
        conditions = []
        if status:
            conditions.append("status = ?")
            params.append(status)
        if category:
            conditions.append("category = ?")
            params.append(category)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        # Sort tasks by due date / scheduled time / id
        query += " ORDER BY due_date ASC, scheduled_time ASC, id ASC"

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def create_goal(
        self,
        title: str,
        description: str | None = None,
        category: str | None = None,
        target_date: str | None = None,
    ) -> dict[str, Any]:
        with db_lock:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO goals (title, description, category, status, target_date)
                   VALUES (?, ?, ?, 'ongoing', ?)""",
                (title, description, category, target_date),
            )
            goal_id = cursor.lastrowid
            conn.commit()
            conn.close()
        return self.get_goal(goal_id)

    def get_goal(self, goal_id: int) -> dict[str, Any] | None:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM goals WHERE id = ?", (goal_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def update_goal(self, goal_id: int, **kwargs) -> dict[str, Any]:
        valid_cols = {"title", "description", "category", "status", "target_date"}
        updates = {k: v for k, v in kwargs.items() if k in valid_cols}
        if not updates:
            return self.get_goal(goal_id)

        sql = (
            "UPDATE goals SET "
            + ", ".join([f"{k} = ?" for k in updates.keys()])
            + " WHERE id = ?"
        )
        params = [*list(updates.values()), goal_id]

        with db_lock:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(sql, params)
            conn.commit()
            conn.close()
        return self.get_goal(goal_id)

    def delete_goal(self, goal_id: int) -> bool:
        with db_lock:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM goals WHERE id = ?", (goal_id,))
            changes = conn.total_changes
            conn.commit()
            conn.close()
        return changes > 0

    def list_goals(self) -> list[dict[str, Any]]:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM goals ORDER BY target_date ASC, id ASC")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def set_preference(self, key: str, value: Any) -> None:
        val_str = json.dumps(value)
        with db_lock:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO preferences (key, value) VALUES (?, ?)",
                (key, val_str),
            )
            conn.commit()
            conn.close()

    def get_preference(self, key: str, default: Any = None) -> Any:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM preferences WHERE key = ?", (key,))
        row = cursor.fetchone()
        conn.close()
        if row:
            try:
                return json.loads(row["value"])
            except Exception:
                return row["value"]
        return default

    # Reminders
    def create_reminder(self, task_id: int, reminder_time: str) -> dict[str, Any]:
        with db_lock:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO reminders
                   (task_id, reminder_time, message, delivery_type, status, is_sent)
                   VALUES (?, ?, ?, ?, 'pending', 0)""",
                (task_id, reminder_time, None, "task"),
            )
            reminder_id = cursor.lastrowid
            conn.commit()
            conn.close()
        return {
            "id": reminder_id,
            "task_id": task_id,
            "reminder_time": reminder_time,
            "message": None,
            "delivery_type": "task",
            "status": "pending",
            "is_sent": 0,
        }

    def create_reminder_entry(
        self,
        task_id: int,
        reminder_time: str,
        message: str | None = None,
        delivery_type: str = "task",
    ) -> dict[str, Any]:
        with db_lock:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO reminders
                   (task_id, reminder_time, message, delivery_type, status, is_sent)
                   VALUES (?, ?, ?, ?, 'pending', 0)""",
                (task_id, reminder_time, message, delivery_type),
            )
            reminder_id = cursor.lastrowid
            conn.commit()
            conn.close()
        return self.get_reminder(reminder_id)

    def get_reminder(self, reminder_id: int) -> dict[str, Any] | None:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM reminders WHERE id = ?", (reminder_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def list_reminders(
        self, task_id: int | None = None, only_pending: bool = True
    ) -> list[dict[str, Any]]:
        conn = get_db_connection()
        cursor = conn.cursor()
        query = "SELECT * FROM reminders"
        conditions = []
        params = []
        if task_id:
            conditions.append("task_id = ?")
            params.append(task_id)
        if only_pending:
            conditions.append("is_sent = 0")
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def update_reminder(self, reminder_id: int, **kwargs) -> dict[str, Any] | None:
        valid_cols = {"reminder_time", "message", "delivery_type", "status", "is_sent"}
        updates = {k: v for k, v in kwargs.items() if k in valid_cols}
        if not updates:
            return self.get_reminder(reminder_id)
        sql = (
            "UPDATE reminders SET "
            + ", ".join([f"{k} = ?" for k in updates.keys()])
            + " WHERE id = ?"
        )
        params = [*list(updates.values()), reminder_id]
        with db_lock:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(sql, params)
            conn.commit()
            conn.close()
        return self.get_reminder(reminder_id)

    def mark_reminder_sent(self, reminder_id: int) -> None:
        self.update_reminder(reminder_id, is_sent=1, status="sent")

    # Notifications
    def create_notification(
        self,
        source_type: str,
        source_id: int | None,
        title: str,
        message: str,
        severity: str = "info",
        scheduled_for: str | None = None,
        status: str = "pending",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with db_lock:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO notifications
                   (source_type, source_id, title, message, severity, scheduled_for, status, metadata)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    source_type,
                    source_id,
                    title,
                    message,
                    severity,
                    scheduled_for,
                    status,
                    json.dumps(metadata or {}),
                ),
            )
            notification_id = cursor.lastrowid
            conn.commit()
            conn.close()
        return self.get_notification(notification_id)

    def get_notification(self, notification_id: int) -> dict[str, Any] | None:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM notifications WHERE id = ?", (notification_id,))
        row = cursor.fetchone()
        conn.close()
        return self._decode_notification(row)

    def list_notifications(
        self, status: str | None = None, limit: int | None = None
    ) -> list[dict[str, Any]]:
        with db_lock:
            conn = get_db_connection()
            cursor = conn.cursor()
            # Automatically clean/purge orphan notifications where the referenced task no longer exists
            cursor.execute("""
                DELETE FROM notifications
                WHERE (source_type = 'task_overdue' AND source_id NOT IN (SELECT id FROM tasks))
                   OR (json_extract(metadata, '$.task_id') IS NOT NULL AND json_extract(metadata, '$.task_id') NOT IN (SELECT id FROM tasks))
            """)
            conn.commit()

            query = "SELECT * FROM notifications"
            params = []
            if status:
                query += " WHERE status = ?"
                params.append(status)
            query += " ORDER BY COALESCE(scheduled_for, delivered_at) DESC, id DESC"
            if limit:
                query += " LIMIT ?"
                params.append(limit)
            cursor.execute(query, params)
            rows = cursor.fetchall()
            conn.close()
        return [self._decode_notification(row) for row in rows]

    def update_notification(self, notification_id: int, **kwargs) -> dict[str, Any] | None:
        valid_cols = {
            "title",
            "message",
            "severity",
            "scheduled_for",
            "delivered_at",
            "status",
            "metadata",
        }
        updates = {}
        for key, value in kwargs.items():
            if key not in valid_cols:
                continue
            updates[key] = json.dumps(value) if key == "metadata" and value is not None else value
        if not updates:
            return self.get_notification(notification_id)
        sql = (
            "UPDATE notifications SET "
            + ", ".join([f"{k} = ?" for k in updates.keys()])
            + " WHERE id = ?"
        )
        params = [*list(updates.values()), notification_id]
        with db_lock:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(sql, params)
            conn.commit()
            conn.close()
        return self.get_notification(notification_id)

    def find_notification(
        self,
        source_type: str,
        source_id: int | None,
        status: str | None = None,
    ) -> dict[str, Any] | None:
        conn = get_db_connection()
        cursor = conn.cursor()
        query = "SELECT * FROM notifications WHERE source_type = ? AND source_id IS ?"
        params: list[Any] = [source_type, source_id]
        if status:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY id DESC LIMIT 1"
        cursor.execute(query, params)
        row = cursor.fetchone()
        conn.close()
        return self._decode_notification(row)

    def _decode_notification(self, row: Any) -> dict[str, Any] | None:
        if not row:
            return None
        notification = dict(row)
        try:
            notification["metadata"] = json.loads(notification["metadata"] or "{}")
        except Exception:
            notification["metadata"] = {}
        return notification

    # Habits
    def create_habit(
        self,
        title: str,
        description: str | None = None,
        category: str = "Personal",
        frequency: str = "daily",
        target_count: int = 1,
        start_date: str | None = None,
        reminder_time: str | None = None,
        goal_id: int | None = None,
    ) -> dict[str, Any]:
        with db_lock:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO habits
                   (title, description, category, frequency, target_count, status, start_date, reminder_time, goal_id)
                   VALUES (?, ?, ?, ?, ?, 'active', ?, ?, ?)""",
                (
                    title,
                    description,
                    category,
                    frequency,
                    target_count,
                    start_date,
                    reminder_time,
                    goal_id,
                ),
            )
            habit_id = cursor.lastrowid
            conn.commit()
            conn.close()
        return self.get_habit(habit_id)

    def get_habit(self, habit_id: int) -> dict[str, Any] | None:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM habits WHERE id = ?", (habit_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def update_habit(self, habit_id: int, **kwargs) -> dict[str, Any] | None:
        valid_cols = {
            "title",
            "description",
            "category",
            "frequency",
            "target_count",
            "status",
            "start_date",
            "reminder_time",
            "goal_id",
            "streak_current",
            "streak_best",
            "last_completed_date",
        }
        updates = {k: v for k, v in kwargs.items() if k in valid_cols}
        if not updates:
            return self.get_habit(habit_id)
        sql = (
            "UPDATE habits SET "
            + ", ".join([f"{k} = ?" for k in updates.keys()])
            + " WHERE id = ?"
        )
        params = [*list(updates.values()), habit_id]
        with db_lock:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(sql, params)
            conn.commit()
            conn.close()
        return self.get_habit(habit_id)

    def list_habits(self, status: str | None = None) -> list[dict[str, Any]]:
        conn = get_db_connection()
        cursor = conn.cursor()
        query = "SELECT * FROM habits"
        params = []
        if status:
            query += " WHERE status = ?"
            params.append(status)
        query += " ORDER BY id ASC"
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def create_habit_log(
        self,
        habit_id: int,
        log_date: str,
        completed_count: int = 1,
        notes: str | None = None,
    ) -> dict[str, Any]:
        with db_lock:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO habit_logs (habit_id, log_date, completed_count, notes)
                   VALUES (?, ?, ?, ?)""",
                (habit_id, log_date, completed_count, notes),
            )
            log_id = cursor.lastrowid
            conn.commit()
            conn.close()
        return self.get_habit_log(log_id)

    def get_habit_log(self, log_id: int) -> dict[str, Any] | None:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM habit_logs WHERE id = ?", (log_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def list_habit_logs(
        self, habit_id: int | None = None, limit: int | None = None
    ) -> list[dict[str, Any]]:
        conn = get_db_connection()
        cursor = conn.cursor()
        query = "SELECT * FROM habit_logs"
        params = []
        if habit_id is not None:
            query += " WHERE habit_id = ?"
            params.append(habit_id)
        query += " ORDER BY log_date DESC, id DESC"
        if limit:
            query += " LIMIT ?"
            params.append(limit)
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    # Memory
    def create_memory_entry(
        self,
        memory_type: str,
        content: str,
        tags: list[str] | None = None,
        related_goal_id: int | None = None,
        related_task_id: int | None = None,
        importance: int = 3,
        created_at: str | None = None,
    ) -> dict[str, Any]:
        with db_lock:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO memory_entries
                   (memory_type, content, tags, related_goal_id, related_task_id, importance, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    memory_type,
                    content,
                    json.dumps(tags or []),
                    related_goal_id,
                    related_task_id,
                    importance,
                    created_at,
                ),
            )
            memory_id = cursor.lastrowid
            conn.commit()
            conn.close()
        return self.get_memory_entry(memory_id)

    def get_memory_entry(self, memory_id: int) -> dict[str, Any] | None:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM memory_entries WHERE id = ?", (memory_id,))
        row = cursor.fetchone()
        conn.close()
        return self._decode_memory(row)

    def update_memory_entry(self, memory_id: int, **kwargs) -> dict[str, Any] | None:
        valid_cols = {
            "memory_type",
            "content",
            "tags",
            "related_goal_id",
            "related_task_id",
            "importance",
            "created_at",
            "last_recalled_at",
        }
        updates = {}
        for key, value in kwargs.items():
            if key not in valid_cols:
                continue
            updates[key] = json.dumps(value) if key == "tags" and value is not None else value
        if not updates:
            return self.get_memory_entry(memory_id)
        sql = (
            "UPDATE memory_entries SET "
            + ", ".join([f"{k} = ?" for k in updates.keys()])
            + " WHERE id = ?"
        )
        params = [*list(updates.values()), memory_id]
        with db_lock:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(sql, params)
            conn.commit()
            conn.close()
        return self.get_memory_entry(memory_id)

    def list_memory_entries(
        self, memory_type: str | None = None, limit: int | None = None
    ) -> list[dict[str, Any]]:
        conn = get_db_connection()
        cursor = conn.cursor()
        query = "SELECT * FROM memory_entries"
        params = []
        if memory_type:
            query += " WHERE memory_type = ?"
            params.append(memory_type)
        query += " ORDER BY importance DESC, created_at DESC, id DESC"
        if limit:
            query += " LIMIT ?"
            params.append(limit)
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        return [self._decode_memory(row) for row in rows]

    def _decode_memory(self, row: Any) -> dict[str, Any] | None:
        if not row:
            return None
        memory = dict(row)
        try:
            memory["tags"] = json.loads(memory["tags"] or "[]")
        except Exception:
            memory["tags"] = []
        return memory

    # Productivity logs
    def set_productivity_log(self, date_str: str, log_data: dict[str, Any]) -> None:
        val_str = json.dumps(log_data)
        with db_lock:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO productivity_logs (date, log_data) VALUES (?, ?)",
                (date_str, val_str),
            )
            conn.commit()
            conn.close()

    def get_productivity_log(self, date_str: str) -> dict[str, Any] | None:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT log_data FROM productivity_logs WHERE date = ?", (date_str,)
        )
        row = cursor.fetchone()
        conn.close()
        if row:
            return json.loads(row["log_data"])
        return None

    # --- Categories ---

    def create_category(self, name: str) -> dict[str, Any]:
        """Creates a category. If the name already exists returns the existing row."""
        name = name.strip()
        with db_lock:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR IGNORE INTO categories (name) VALUES (?)", (name,)
            )
            conn.commit()
            cursor.execute("SELECT * FROM categories WHERE name = ?", (name,))
            row = cursor.fetchone()
            conn.close()
        return dict(row) if row else {"id": -1, "name": name}

    def list_categories(self) -> list[dict[str, Any]]:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM categories ORDER BY name ASC")
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def rename_category(self, category_id: int, new_name: str) -> dict[str, Any] | None:
        """Renames a category and updates all tasks/habits/goals that used the old name."""
        new_name = new_name.strip()
        with db_lock:
            conn = get_db_connection()
            cursor = conn.cursor()
            # Fetch old name first
            cursor.execute("SELECT name FROM categories WHERE id = ?", (category_id,))
            row = cursor.fetchone()
            if not row:
                conn.close()
                return None
            old_name = row["name"]
            # Update the category name
            cursor.execute(
                "UPDATE categories SET name = ? WHERE id = ?", (new_name, category_id)
            )
            # Cascade rename to existing rows in tasks, habits, goals
            cursor.execute(
                "UPDATE tasks SET category = ? WHERE category = ?", (new_name, old_name)
            )
            cursor.execute(
                "UPDATE habits SET category = ? WHERE category = ?", (new_name, old_name)
            )
            cursor.execute(
                "UPDATE goals SET category = ? WHERE category = ?", (new_name, old_name)
            )
            conn.commit()
            cursor.execute("SELECT * FROM categories WHERE id = ?", (category_id,))
            updated = cursor.fetchone()
            conn.close()
        return dict(updated) if updated else None

    def delete_category(self, category_id: int) -> dict[str, bool | str]:
        """Deletes the category row. Tasks keep their category text (orphaned string)."""
        with db_lock:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM categories WHERE id = ?", (category_id,))
            row = cursor.fetchone()
            if not row:
                conn.close()
                return {"deleted": False, "reason": "Category not found."}
            cursor.execute("DELETE FROM categories WHERE id = ?", (category_id,))
            conn.commit()
            conn.close()
        return {"deleted": True}

    def update_task_reminder(self, task_id: int, reminder_time: str | None, title: str) -> None:
        with db_lock:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM reminders WHERE task_id = ? AND is_sent = 0", (task_id,))
            if reminder_time and reminder_time.strip():
                cursor.execute(
                    """INSERT INTO reminders (task_id, reminder_time, message, delivery_type, status, is_sent)
                       VALUES (?, ?, ?, 'task', 'pending', 0)""",
                    (task_id, reminder_time.strip(), f"Reminder: {title}"),
                )
            conn.commit()
            conn.close()

    def notification_exists(self, source_type: str, source_id: int) -> bool:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT 1 FROM notifications WHERE source_type = ? AND source_id = ?",
            (source_type, source_id),
        )
        exists = cursor.fetchone() is not None
        conn.close()
        return exists
