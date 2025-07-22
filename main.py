"""
Release Management Application
Main entry point for the Streamlit application
"""

import streamlit as st
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.append(str(project_root))

from config.settings import APP_CONFIG
from database.db_manager import DatabaseManager
from pages import dashboard, notifications, personal_notes, admin_settings
from utils.session_state import init_session_state
from utils.logging_config import setup_logging
def main():
    """Main application entry point"""

    # Configure Streamlit page
    st.set_page_config(
        page_title=APP_CONFIG["app_name"],
        page_icon="🚀",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # Initialize session state
    init_session_state()

    # Initialize logging
    if 'logging_initialized' not in st.session_state:
        setup_logging()
        st.session_state.logging_initialized = True

    # Initialize database
    db_manager = DatabaseManager()

    # Start background scheduler
    """if 'scheduler_started' not in st.session_state:
        start_background_scheduler()
        st.session_state.scheduler_started = True"""

    # Custom CSS for professional look
    st.markdown("""
    <style>
    .main-header {
        font-size: 2.5rem;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
        font-weight: bold;
    }
    .sidebar-header {
        font-size: 1.5rem;
        color: #2e7d32;
        margin-bottom: 1rem;
    }
    .metric-card {
        background: linear-gradient(90deg, #f0f2f6, #ffffff);
        padding: 1rem;
        border-radius: 10px;
        border: 1px solid #e1e5e9;
        margin: 0.5rem 0;
    }
    .warning-box {
        background-color: #fff3cd;
        border: 1px solid #ffeaa7;
        border-radius: 5px;
        padding: 1rem;
        margin: 1rem 0;
    }
    .success-box {
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        border-radius: 5px;
        padding: 1rem;
        margin: 1rem 0;
    }
    </style>
    """, unsafe_allow_html=True)

    # Main header
    st.markdown('<div class="main-header">🚀 Release Management Dashboard</div>',
                unsafe_allow_html=True)

    # Sidebar navigation
    with st.sidebar:
        st.markdown('<div class="sidebar-header">📋 Navigation</div>',
                    unsafe_allow_html=True)

        # Current release info
        current_release = st.session_state.current_release
        st.info(f"**Current Release:** {current_release['id']}")
        st.info(f"**Period:** {current_release['start_date']} to {current_release['end_date']}")

        st.markdown("---")

        # Page selection
        page = st.selectbox(
            "Choose a page:",
            ["Dashboard", "Notifications", "Personal Notes", "Admin & Settings"],
            index=0
        )

        st.markdown("---")

        # Release selector
        st.markdown("**📅 Release Management**")
        available_releases = [
            "week2025.30", "week2025.29", "week2025.28",
            "week2025.27", "week2025.26"
        ]

        selected_release = st.selectbox(
            "Select Release:",
            available_releases,
            index=0
        )

        if selected_release != current_release['id']:
            if st.button("Switch Release"):
                st.session_state.current_release = {
                    'id': selected_release,
                    'start_date': '2025-07-21',  # This would be calculated
                    'end_date': '2025-07-27'
                }
                st.rerun()

    # Route to appropriate page
    if page == "Dashboard":
        dashboard.show_dashboard(db_manager)
    elif page == "Notifications":
        notifications.show_notifications(db_manager)
    elif page == "Personal Notes":
        personal_notes.show_personal_notes(db_manager)
    elif page == "Admin & Settings":
        admin_settings.show_admin_settings(db_manager)

if __name__ == "__main__":
    main()