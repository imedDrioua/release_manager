"""
Database Manager for Release Management Application
File: database/db_manager.py
"""

import sqlite3
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional
from contextlib import contextmanager

from config.settings import DATABASE_CONFIG

class DatabaseManager:
    def __init__(self):
        self.db_path = DATABASE_CONFIG["db_path"]
        self._ensure_db_directory()
        self._initialize_database()

    def _ensure_db_directory(self):
        """Ensure the database directory exists"""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

    def _initialize_database(self):
        """Initialize the database with required tables"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Releases table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS releases (
                    id TEXT PRIMARY KEY,
                    start_date DATE NOT NULL,
                    end_date DATE NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'active'
                )
            """)

            # JIRA tickets current state
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS jira_tickets (
                    key TEXT PRIMARY KEY,
                    release_id TEXT NOT NULL,
                    summary TEXT,
                    status TEXT,
                    assignee TEXT,
                    priority TEXT,
                    issue_type TEXT,
                    reporter TEXT,
                    created_date TIMESTAMP,
                    updated_date TIMESTAMP,
                    raw_data JSON,
                    last_synced TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (release_id) REFERENCES releases(id)
                )
            """)

            # JIRA tickets historical snapshots (for notifications)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS jira_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticket_key TEXT NOT NULL,
                    release_id TEXT NOT NULL,
                    snapshot_date TIMESTAMP NOT NULL,
                    field_name TEXT NOT NULL,
                    old_value TEXT,
                    new_value TEXT,
                    changed_by TEXT,
                    raw_data JSON,
                    FOREIGN KEY (release_id) REFERENCES releases(id)
                )
            """)

            # Weekly snapshots for comparison
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS weekly_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    release_id TEXT NOT NULL,
                    snapshot_date TIMESTAMP NOT NULL,
                    ticket_data JSON NOT NULL,
                    FOREIGN KEY (release_id) REFERENCES releases(id)
                )
            """)

            # Personal notes
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS personal_notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticket_key TEXT,
                    release_id TEXT,
                    note_type TEXT CHECK (note_type IN ('ticket', 'release')),
                    title TEXT,
                    content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    tags TEXT
                )
            """)

            # Notifications
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS notifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticket_key TEXT NOT NULL,
                    release_id TEXT NOT NULL,
                    notification_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    message TEXT NOT NULL,
                    is_read BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    metadata JSON
                )
            """)

            # Convention violations
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS convention_violations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticket_key TEXT NOT NULL,
                    release_id TEXT NOT NULL,
                    violation_type TEXT NOT NULL,
                    description TEXT NOT NULL,
                    severity TEXT CHECK (severity IN ('low', 'medium', 'high')),
                    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    resolved BOOLEAN DEFAULT FALSE
                )
            """)

            conn.commit()

    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Enable column access by name
        try:
            yield conn
        finally:
            conn.close()

    # Release Management
    def create_release(self, release_id: str, start_date: str, end_date: str) -> bool:
        """Create a new release"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO releases (id, start_date, end_date)
                    VALUES (?, ?, ?)
                """, (release_id, start_date, end_date))
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Error creating release: {e}")
            return False

    def get_release(self, release_id: str) -> Optional[Dict]:
        """Get release information"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM releases WHERE id = ?", (release_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_all_releases(self) -> List[Dict]:
        """Get all releases"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM releases ORDER BY start_date DESC")
            return [dict(row) for row in cursor.fetchall()]

    # JIRA Tickets Management
    def upsert_jira_ticket(self, ticket_data: Dict) -> bool:
        """Insert or update JIRA ticket"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO jira_tickets 
                    (key, release_id, summary, status, assignee, priority, issue_type, 
                     reporter, created_date, updated_date, raw_data)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    ticket_data['key'],
                    ticket_data['release_id'],
                    ticket_data.get('summary'),
                    ticket_data.get('status'),
                    ticket_data.get('assignee'),
                    ticket_data.get('priority'),
                    ticket_data.get('issue_type'),
                    ticket_data.get('reporter'),
                    ticket_data.get('created_date'),
                    ticket_data.get('updated_date'),
                    json.dumps(ticket_data.get('raw_data', {}))
                ))
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Error upserting JIRA ticket: {e}")
            return False

    def get_tickets_for_release(self, release_id: str) -> List[Dict]:
        """Get all tickets for a specific release"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM jira_tickets 
                WHERE release_id = ?
                ORDER BY updated_date DESC
            """, (release_id,))
            tickets = []
            for row in cursor.fetchall():
                ticket = dict(row)
                if ticket['raw_data']:
                    ticket['raw_data'] = json.loads(ticket['raw_data'])
                tickets.append(ticket)
            return tickets

    def get_ticket_statistics(self, release_id: str) -> Dict:
        """Get ticket statistics for a release"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Total tickets
            cursor.execute("SELECT COUNT(*) FROM jira_tickets WHERE release_id = ?", (release_id,))
            total = cursor.fetchone()[0]

            # By status
            cursor.execute("""
                SELECT status, COUNT(*) FROM jira_tickets 
                WHERE release_id = ? 
                GROUP BY status
            """, (release_id,))
            by_status = dict(cursor.fetchall())

            # By priority
            cursor.execute("""
                SELECT priority, COUNT(*) FROM jira_tickets 
                WHERE release_id = ? 
                GROUP BY priority
            """, (release_id,))
            by_priority = dict(cursor.fetchall())

            return {
                'total': total,
                'by_status': by_status,
                'by_priority': by_priority
            }

    # Notifications Management
    def create_weekly_snapshot(self, release_id: str, tickets_data: List[Dict]) -> bool:
        """Create a weekly snapshot for comparison"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO weekly_snapshots (release_id, snapshot_date, ticket_data)
                    VALUES (?, ?, ?)
                """, (release_id, datetime.now(), json.dumps(tickets_data)))
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Error creating weekly snapshot: {e}")
            return False

    def get_last_snapshot(self, release_id: str) -> Optional[Dict]:
        """Get the last weekly snapshot"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM weekly_snapshots 
                WHERE release_id = ?
                ORDER BY snapshot_date DESC
                LIMIT 1
            """, (release_id,))
            row = cursor.fetchone()
            if row:
                snapshot = dict(row)
                snapshot['ticket_data'] = json.loads(snapshot['ticket_data'])
                return snapshot
            return None

    def create_notification(self, ticket_key: str, release_id: str,
                            notification_type: str, title: str, message: str,
                            metadata: Dict = None) -> bool:
        """Create a notification"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO notifications 
                    (ticket_key, release_id, notification_type, title, message, metadata)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (ticket_key, release_id, notification_type, title, message,
                      json.dumps(metadata or {})))
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Error creating notification: {e}")
            return False

    def get_notifications(self, release_id: str, show_read: bool = False) -> List[Dict]:
        """Get notifications for a release"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            query = """
                SELECT * FROM notifications 
                WHERE release_id = ?
            """
            if not show_read:
                query += " AND is_read = FALSE"
            query += " ORDER BY created_at DESC"

            cursor.execute(query, (release_id,))
            notifications = []
            for row in cursor.fetchall():
                notification = dict(row)
                notification['metadata'] = json.loads(notification['metadata'])
                notifications.append(notification)
            return notifications

    def mark_notification_read(self, notification_id: int) -> bool:
        """Mark a notification as read"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE notifications SET is_read = TRUE WHERE id = ?
                """, (notification_id,))
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Error marking notification as read: {e}")
            return False

    # Personal Notes Management
    def create_note(self, title: str, content: str, note_type: str,
                    ticket_key: str = None, release_id: str = None,
                    tags: str = None) -> bool:
        """Create a personal note"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO personal_notes 
                    (title, content, note_type, ticket_key, release_id, tags)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (title, content, note_type, ticket_key, release_id, tags))
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Error creating note: {e}")
            return False

    def get_notes(self, note_type: str = None, release_id: str = None,
                  ticket_key: str = None) -> List[Dict]:
        """Get personal notes with optional filtering"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM personal_notes WHERE 1=1"
            params = []

            if note_type:
                query += " AND note_type = ?"
                params.append(note_type)
            if release_id:
                query += " AND release_id = ?"
                params.append(release_id)
            if ticket_key:
                query += " AND ticket_key = ?"
                params.append(ticket_key)

            query += " ORDER BY updated_at DESC"
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def update_note(self, note_id: int, title: str, content: str, tags: str = None) -> bool:
        """Update a personal note"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE personal_notes 
                    SET title = ?, content = ?, tags = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (title, content, tags, note_id))
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Error updating note: {e}")
            return False

    def delete_note(self, note_id: int) -> bool:
        """Delete a personal note"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM personal_notes WHERE id = ?", (note_id,))
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Error deleting note: {e}")
            return False