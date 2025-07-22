# config/__init__.py
"""Configuration package for Release Management Application"""

from .settings import (
    APP_CONFIG,
    JIRA_CONFIG,
    DATABASE_CONFIG,
    get_current_release,
    get_release_dates
)

__all__ = [
    'APP_CONFIG',
    'JIRA_CONFIG',
    'DATABASE_CONFIG',
    'get_current_release',
    'get_release_dates'
]

# database/__init__.py
"""Database package for Release Management Application"""

from .db_manager import DatabaseManager

__all__ = ['DatabaseManager']

# services/__init__.py
"""Services package for Release Management Application"""

from .jira_service import JiraService

__all__ = ['JiraService']

# pages/__init__.py
"""Pages package for Release Management Application"""

from . import dashboard, notifications, personal_notes

__all__ = ['dashboard', 'notifications', 'personal_notes']

# utils/__init__.py
"""Utilities package for Release Management Application"""

from .session_state import (
    init_session_state,
    update_current_release,
    get_current_release_id,
    set_selected_ticket,
    get_selected_ticket
)

__all__ = [
    'init_session_state',
    'update_current_release',
    'get_current_release_id',
    'set_selected_ticket',
    'get_selected_ticket'
]

# scripts/__init__.py
"""Scripts package for Release Management Application"""

__all__ = []