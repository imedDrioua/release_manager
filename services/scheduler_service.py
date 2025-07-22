"""
Scheduler Service for Release Management Application
File: services/scheduler_service.py
"""

import schedule
import time
import threading
import logging
from datetime import datetime, timedelta
from typing import Callable, Dict, Any

from database.db_manager import DatabaseManager
from services.jira_service import JiraService
from config.settings import get_current_release, NOTIFICATION_CONFIG
from utils.logging_config import get_logger

class SchedulerService:
    def __init__(self):
        self.logger = get_logger('scheduler')
        self.db_manager = DatabaseManager()
        self.jira_service = JiraService()
        self.running = False
        self.scheduler_thread = None

        # Initialize scheduled jobs
        self._setup_schedules()

    def _setup_schedules(self):
        """Setup scheduled jobs"""

        # Weekly snapshot every Friday at 5 PM
        schedule.every().friday.at("17:00").do(self._create_weekly_snapshot)

        # Daily cleanup of old data
        schedule.every().day.at("02:00").do(self._cleanup_old_data)

        # Hourly JIRA sync (if needed)
        # schedule.every().hour.do(self._sync_jira_data)

        self.logger.info("Scheduled jobs configured")

    def start(self):
        """Start the scheduler in a separate thread"""
        if not self.running:
            self.running = True
            self.scheduler_thread = threading.Thread(target=self._run_scheduler, daemon=True)
            self.scheduler_thread.start()
            self.logger.info("Scheduler service started")

    def stop(self):
        """Stop the scheduler"""
        self.running = False
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=5)
        self.logger.info("Scheduler service stopped")

    def _run_scheduler(self):
        """Main scheduler loop"""
        while self.running:
            try:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
            except Exception as e:
                self.logger.error(f"Scheduler error: {e}")
                time.sleep(300)  # Wait 5 minutes on error

    def _create_weekly_snapshot(self):
        """Create weekly snapshot for current release"""
        try:
            current_release = get_current_release()
            self.logger.info(f"Creating weekly snapshot for {current_release}")

            # Get current tickets from JIRA
            tickets = self.jira_service.get_tickets_for_release(current_release)

            # Store tickets in database
            for ticket in tickets:
                ticket_data = {
                    'key': ticket['key'],
                    'release_id': current_release,
                    'summary': ticket['summary'],
                    'status': ticket['status'],
                    'assignee': ticket.get('assignee'),
                    'priority': ticket['priority'],
                    'issue_type': ticket['issueType'],
                    'reporter': ticket.get('reporter'),
                    'created_date': ticket['created'],
                    'updated_date': ticket['updated'],
                    'raw_data': ticket
                }
                self.db_manager.upsert_jira_ticket(ticket_data)

            # Create snapshot
            success = self.db_manager.create_weekly_snapshot(current_release, tickets)

            if success:
                self.logger.info(f"Weekly snapshot created successfully for {current_release}")

                # Create notification about snapshot creation
                self.db_manager.create_notification(
                    ticket_key="SYSTEM",
                    release_id=current_release,
                    notification_type="snapshot_created",
                    title="Weekly Snapshot Created",
                    message=f"Automated snapshot created for {current_release} with {len(tickets)} tickets",
                    metadata={'ticket_count': len(tickets)}
                )
            else:
                self.logger.error(f"Failed to create weekly snapshot for {current_release}")

        except Exception as e:
            self.logger.error(f"Error creating weekly snapshot: {e}")

    def _cleanup_old_data(self):
        """Cleanup old data based on retention policy"""
        try:
            retention_days = NOTIFICATION_CONFIG.get('retention_days', 30)
            cutoff_date = datetime.now() - timedelta(days=retention_days)

            self.logger.info(f"Starting data cleanup for records older than {retention_days} days")

            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Clean old notifications
                cursor.execute("""
                    DELETE FROM notifications 
                    WHERE created_at < ? AND is_read = TRUE
                """, (cutoff_date,))

                deleted_notifications = cursor.rowcount

                # Clean old snapshots (keep at least 4 weeks)
                cursor.execute("""
                    DELETE FROM weekly_snapshots 
                    WHERE snapshot_date < ?
                """, (cutoff_date,))

                deleted_snapshots = cursor.rowcount

                # Clean old convention violations
                cursor.execute("""
                    DELETE FROM convention_violations 
                    WHERE detected_at < ? AND resolved = TRUE
                """, (cutoff_date,))

                deleted_violations = cursor.rowcount

                conn.commit()

                self.logger.info(f"Cleanup completed: {deleted_notifications} notifications, "
                                 f"{deleted_snapshots} snapshots, {deleted_violations} violations deleted")

        except Exception as e:
            self.logger.error(f"Error during data cleanup: {e}")

    def _sync_jira_data(self):
        """Sync JIRA data for current release"""
        try:
            current_release = get_current_release()
            self.logger.info(f"Syncing JIRA data for {current_release}")

            # This would be used for real-time sync if needed
            success = self.jira_service.refresh_ticket_data(current_release)

            if success:
                self.logger.info(f"JIRA data sync completed for {current_release}")
            else:
                self.logger.warning(f"JIRA data sync failed for {current_release}")

        except Exception as e:
            self.logger.error(f"Error syncing JIRA data: {e}")

    def get_scheduler_status(self) -> Dict[str, Any]:
        """Get scheduler status information"""
        jobs = []
        for job in schedule.jobs:
            jobs.append({
                'job_func': job.job_func.__name__,
                'next_run': job.next_run.isoformat() if job.next_run else None,
                'interval': str(job.interval),
                'unit': job.unit
            })

        return {
            'running': self.running,
            'jobs_count': len(schedule.jobs),
            'jobs': jobs
        }

# Global scheduler instance
_scheduler_instance = None

def get_scheduler() -> SchedulerService:
    """Get singleton scheduler instance"""
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = SchedulerService()
    return _scheduler_instance

def start_background_scheduler():
    """Start the background scheduler"""
    scheduler = get_scheduler()
    scheduler.start()

def stop_background_scheduler():
    """Stop the background scheduler"""
    scheduler = get_scheduler()
    scheduler.stop()

# Monitoring utilities
class SystemMonitor:
    """System monitoring utilities"""

    def __init__(self):
        self.logger = get_logger('monitor')
        self.db_manager = DatabaseManager()

    def get_system_health(self) -> Dict[str, Any]:
        """Get system health metrics"""
        try:
            health = {
                'database': self._check_database_health(),
                'scheduler': self._check_scheduler_health(),
                'data_freshness': self._check_data_freshness()
            }

            # Overall health score
            health_scores = []
            for component, status in health.items():
                if isinstance(status, dict) and 'healthy' in status:
                    health_scores.append(1 if status['healthy'] else 0)

            health['overall'] = {
                'healthy': sum(health_scores) == len(health_scores),
                'score': sum(health_scores) / len(health_scores) if health_scores else 0
            }

            return health

        except Exception as e:
            self.logger.error(f"Error checking system health: {e}")
            return {'error': str(e)}

    def _check_database_health(self) -> Dict[str, Any]:
        """Check database connectivity and basic operations"""
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM releases")
                release_count = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM jira_tickets")
                ticket_count = cursor.fetchone()[0]

                return {
                    'healthy': True,
                    'release_count': release_count,
                    'ticket_count': ticket_count,
                    'last_check': datetime.now().isoformat()
                }
        except Exception as e:
            return {
                'healthy': False,
                'error': str(e),
                'last_check': datetime.now().isoformat()
            }

    def _check_scheduler_health(self) -> Dict[str, Any]:
        """Check scheduler status"""
        try:
            scheduler = get_scheduler()
            status = scheduler.get_scheduler_status()

            return {
                'healthy': status['running'],
                'jobs_count': status['jobs_count'],
                'running': status['running'],
                'last_check': datetime.now().isoformat()
            }
        except Exception as e:
            return {
                'healthy': False,
                'error': str(e),
                'last_check': datetime.now().isoformat()
            }

    def _check_data_freshness(self) -> Dict[str, Any]:
        """Check data freshness"""
        try:
            current_release = get_current_release()
            tickets = self.db_manager.get_tickets_for_release(current_release)

            if not tickets:
                return {
                    'healthy': False,
                    'reason': 'No tickets found for current release',
                    'last_check': datetime.now().isoformat()
                }

            # Check when tickets were last updated
            latest_update = max(
                datetime.fromisoformat(ticket['last_synced'].replace('Z', ''))
                for ticket in tickets
                if ticket.get('last_synced')
            )

            hours_since_update = (datetime.now() - latest_update).total_seconds() / 3600

            return {
                'healthy': hours_since_update < 24,  # Data should be less than 24 hours old
                'hours_since_update': round(hours_since_update, 1),
                'latest_update': latest_update.isoformat(),
                'last_check': datetime.now().isoformat()
            }

        except Exception as e:
            return {
                'healthy': False,
                'error': str(e),
                'last_check': datetime.now().isoformat()
            }