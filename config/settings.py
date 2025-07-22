"""
Configuration settings for the Release Management Application
File: config/settings.py
"""

import os
from datetime import datetime, timedelta

# Application Configuration
APP_CONFIG = {
    "app_name": "Release Management System",
    "version": "1.0.0",
    "release_format": "week{year}.{week}",
}

# Database Configuration
DATABASE_CONFIG = {
    "db_path": "data/release_management.db",
    "backup_path": "data/backups/",
}

# JIRA Configuration
JIRA_CONFIG = {
    "server_url": os.getenv("JIRA_SERVER_URL", "https://your-company.atlassian.net"),
    "username": os.getenv("JIRA_USERNAME", "your-username"),
    "api_token": os.getenv("JIRA_API_TOKEN", "your-api-token"),
    "project_key": os.getenv("JIRA_PROJECT_KEY", "PROJ"),
}

# JQL Queries
JQL_QUERIES = {
    "current_release": "fixVersion = '{release_id}' AND status != 'Closed'",
    "all_release_tickets": "fixVersion = '{release_id}'",
    "high_priority": "fixVersion = '{release_id}' AND priority in ('High', 'Highest')",
    "blocked_tickets": "fixVersion = '{release_id}' AND status = 'Blocked'",
}

# JIRA Fields to fetch
JIRA_FIELDS = [
    "summary",
    "status",
    "assignee",
    "priority",
    "created",
    "updated",
    "fixVersions",
    "components",
    "labels",
    "issueType",
    "reporter",
    "description",
]

# Workflow Convention Rules (dummy implementation)
WORKFLOW_CONVENTIONS = {
    "status_transitions": {
        "To Do": ["In Progress"],
        "In Progress": ["Done", "Blocked", "In Review"],
        "In Review": ["Done", "In Progress"],
        "Blocked": ["In Progress"],
        "Done": []
    },
    "required_fields": {
        "In Progress": ["assignee"],
        "Done": ["assignee", "resolution"],
    },
    "time_limits": {
        "In Progress": 5,  # days
        "In Review": 2,  # days
    }
}

# Notification Settings
NOTIFICATION_CONFIG = {
    "save_schedule": "fridays_17:00",  # Every Friday at 5 PM
    "retention_days": 30,
    "batch_size": 100,
}

# UI Configuration
UI_CONFIG = {
    "items_per_page": 20,
    "chart_colors": {
        "primary": "#1f77b4",
        "secondary": "#ff7f0e",
        "success": "#2ca02c",
        "warning": "#d62728",
        "info": "#9467bd",
    },
    "status_colors": {
        "To Do": "#6c757d",
        "In Progress": "#007bff",
        "In Review": "#ffc107",
        "Done": "#28a745",
        "Blocked": "#dc3545",
    }
}

def get_current_release():
    """Generate current release ID based on current date"""
    now = datetime.now()
    year = now.year
    week = now.isocalendar()[1]
    return f"week{year}.{week:02d}"

def get_release_dates(release_id):
    """Calculate start and end dates for a release"""
    # Extract year and week from release_id (e.g., "week2025.30")
    try:
        parts = release_id.split('.')
        year = int(parts[0].replace('week', ''))
        week = int(parts[1])

        # Calculate the start date (Monday) of the given week
        jan_1 = datetime(year, 1, 1)
        if jan_1.weekday() != 0:  # If Jan 1 is not a Monday
            days_to_monday = 7 - jan_1.weekday()
            first_monday = jan_1 + timedelta(days=days_to_monday)
        else:
            first_monday = jan_1

        start_date = first_monday + timedelta(weeks=week-1)
        end_date = start_date + timedelta(days=6)  # Sunday

        return {
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d")
        }
    except:
        # Fallback to current week
        now = datetime.now()
        start_of_week = now - timedelta(days=now.weekday())
        end_of_week = start_of_week + timedelta(days=6)
        return {
            "start_date": start_of_week.strftime("%Y-%m-%d"),
            "end_date": end_of_week.strftime("%Y-%m-%d")
        }