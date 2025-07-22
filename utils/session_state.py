"""
Session State Management for Release Management Application
File: utils/session_state.py
"""

import streamlit as st
from datetime import datetime
from config.settings import get_current_release, get_release_dates

def init_session_state():
    """Initialize session state variables"""

    # Current release information
    if 'current_release' not in st.session_state:
        current_release_id = get_current_release()
        release_dates = get_release_dates(current_release_id)
        st.session_state.current_release = {
            'id': current_release_id,
            'start_date': release_dates['start_date'],
            'end_date': release_dates['end_date']
        }

    # Dashboard state
    if 'dashboard_state' not in st.session_state:
        st.session_state.dashboard_state = {
            'last_refresh': None,
            'selected_ticket': None,
            'selected_field': 'status',
            'tickets_data': [],
            'show_violations': True
        }

    # Notifications state
    if 'notifications_state' not in st.session_state:
        st.session_state.notifications_state = {
            'show_read': False,
            'filter_type': 'all',
            'last_check': None
        }

    # Personal notes state
    if 'notes_state' not in st.session_state:
        st.session_state.notes_state = {
            'selected_note_type': 'release',
            'editing_note': None,
            'search_query': ''
        }

    # UI state
    if 'ui_state' not in st.session_state:
        st.session_state.ui_state = {
            'sidebar_expanded': True,
            'theme': 'light',
            'items_per_page': 20,
            'current_page': 1
        }

def update_current_release(release_id: str):
    """Update the current release in session state"""
    release_dates = get_release_dates(release_id)
    st.session_state.current_release = {
        'id': release_id,
        'start_date': release_dates['start_date'],
        'end_date': release_dates['end_date']
    }

    # Reset dashboard state when switching releases
    st.session_state.dashboard_state = {
        'last_refresh': None,
        'selected_ticket': None,
        'selected_field': 'status',
        'tickets_data': [],
        'show_violations': True
    }

def get_current_release_id():
    """Get current release ID from session state"""
    return st.session_state.current_release['id']

def set_selected_ticket(ticket_key: str):
    """Set the selected ticket in dashboard state"""
    st.session_state.dashboard_state['selected_ticket'] = ticket_key

def get_selected_ticket():
    """Get the selected ticket from dashboard state"""
    return st.session_state.dashboard_state.get('selected_ticket')

def mark_dashboard_refreshed():
    """Mark dashboard as refreshed"""
    st.session_state.dashboard_state['last_refresh'] = datetime.now()

def get_last_refresh():
    """Get last refresh timestamp"""
    return st.session_state.dashboard_state.get('last_refresh')

def update_tickets_data(tickets: list):
    """Update tickets data in session state"""
    st.session_state.dashboard_state['tickets_data'] = tickets

def get_tickets_data():
    """Get tickets data from session state"""
    return st.session_state.dashboard_state.get('tickets_data', [])