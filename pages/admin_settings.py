"""
Administration and Settings Page for Release Management Application
File: pages/admin_settings.py
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import json
import os

from services.scheduler_service import SystemMonitor, get_scheduler
from utils.export_utils import create_export_buttons, generate_dashboard_summary
from utils.logging_config import get_logger
from config.settings import APP_CONFIG, JIRA_CONFIG, DATABASE_CONFIG, WORKFLOW_CONVENTIONS

def show_admin_settings(db_manager):
    """Display the admin and settings page"""

    st.title("⚙️ Administration & Settings")

    # Create tabs for different admin sections
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "🔍 System Health",
        "📊 Analytics",
        "⚙️ Configuration",
        "📁 Data Management",
        "🚀 Advanced"
    ])

    with tab1:
        show_system_health(db_manager)

    with tab2:
        show_analytics_dashboard(db_manager)

    with tab3:
        show_configuration_settings()

    with tab4:
        show_data_management(db_manager)

    with tab5:
        show_advanced_settings(db_manager)

def show_system_health(db_manager):
    """Display system health monitoring"""

    st.subheader("🩺 System Health Monitor")

    # Get system health
    monitor = SystemMonitor()
    health = monitor.get_system_health()

    if 'error' in health:
        st.error(f"Error checking system health: {health['error']}")
        return

    # Overall health status
    overall_healthy = health.get('overall', {}).get('healthy', False)
    health_color = "🟢" if overall_healthy else "🔴"
    st.markdown(f"### {health_color} System Status: {'Healthy' if overall_healthy else 'Issues Detected'}")

    # Health metrics in columns
    col1, col2, col3 = st.columns(3)

    with col1:
        # Database Health
        db_health = health.get('database', {})
        db_status = "✅ Healthy" if db_health.get('healthy') else "❌ Issues"
        st.metric(
            label="Database",
            value=db_status,
            delta=f"{db_health.get('ticket_count', 0)} tickets"
        )

        if not db_health.get('healthy'):
            st.error(f"Database Error: {db_health.get('error', 'Unknown')}")

    with col2:
        # Scheduler Health
        scheduler_health = health.get('scheduler', {})
        scheduler_status = "✅ Running" if scheduler_health.get('healthy') else "❌ Stopped"
        st.metric(
            label="Background Jobs",
            value=scheduler_status,
            delta=f"{scheduler_health.get('jobs_count', 0)} jobs"
        )

        if not scheduler_health.get('healthy'):
            st.error(f"Scheduler Error: {scheduler_health.get('error', 'Not running')}")

    with col3:
        # Data Freshness
        freshness_health = health.get('data_freshness', {})
        freshness_status = "✅ Fresh" if freshness_health.get('healthy') else "⚠️ Stale"
        hours_old = freshness_health.get('hours_since_update', 0)
        st.metric(
            label="Data Freshness",
            value=freshness_status,
            delta=f"{hours_old:.1f}h ago"
        )

        if not freshness_health.get('healthy'):
            st.warning("Data may be outdated. Consider refreshing.")

    # Detailed health information
    st.markdown("---")
    st.subheader("📋 Detailed Health Information")

    for component, status in health.items():
        if component != 'overall' and isinstance(status, dict):
            with st.expander(f"{component.title()} Details"):
                for key, value in status.items():
                    if key != 'healthy':
                        st.write(f"**{key.replace('_', ' ').title()}:** {value}")

    # Manual health check
    if st.button("🔄 Refresh Health Check"):
        st.rerun()

def show_analytics_dashboard(db_manager):
    """Display advanced analytics and metrics"""

    st.subheader("📊 System Analytics")

    try:
        # Get all releases for analysis
        releases = db_manager.get_all_releases()

        if not releases:
            st.info("No releases found for analysis.")
            return

        # Release selector for detailed analysis
        selected_release = st.selectbox(
            "Select Release for Analysis:",
            [r['id'] for r in releases]
        )

        # Get tickets for selected release
        tickets = db_manager.get_tickets_for_release(selected_release)

        if tickets:
            # Generate summary statistics
            stats = generate_dashboard_summary(tickets, selected_release)

            # Key metrics row
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.metric("Total Tickets", stats['total'])
            with col2:
                st.metric("Completion Rate", f"{stats['completion_rate']}%")
            with col3:
                st.metric("High Priority", stats['high_priority'])
            with col4:
                st.metric("Blocked", stats['blocked'])

            # Charts row
            chart_col1, chart_col2 = st.columns(2)

            with chart_col1:
                # Status over time (simulated)
                st.subheader("📈 Status Trends")

                # Create a mock trend chart
                dates = pd.date_range(start='2025-07-15', end='2025-07-22', freq='D')
                trend_data = []
                for date in dates:
                    # Simulate progress over time
                    progress = min(100, (date - dates[0]).days * 15)
                    trend_data.append({
                        'Date': date,
                        'Completion %': progress,
                        'Total Tickets': stats['total']
                    })

                df_trend = pd.DataFrame(trend_data)
                fig = px.line(df_trend, x='Date', y='Completion %',
                              title='Release Progress Over Time')
                st.plotly_chart(fig, use_container_width=True)

            with chart_col2:
                # Team performance
                st.subheader("👥 Team Performance")

                assignee_stats = stats['by_assignee']
                if assignee_stats:
                    df_team = pd.DataFrame([
                        {'Assignee': k, 'Tickets': v}
                        for k, v in assignee_stats.items()
                    ])

                    fig = px.bar(df_team, x='Assignee', y='Tickets',
                                 title='Tickets by Team Member')
                    fig.update_xaxes(tickangle=45)
                    st.plotly_chart(fig, use_container_width=True)

        # Historical analysis
        st.markdown("---")
        st.subheader("📊 Historical Analysis")

        # Compare releases
        if len(releases) > 1:
            release_comparison = []
            for release in releases[-5:]:  # Last 5 releases
                release_tickets = db_manager.get_tickets_for_release(release['id'])
                release_stats = generate_dashboard_summary(release_tickets, release['id'])

                release_comparison.append({
                    'Release': release['id'],
                    'Total Tickets': release_stats['total'],
                    'Completion Rate': release_stats['completion_rate'],
                    'High Priority': release_stats['high_priority'],
                    'Blocked': release_stats['blocked']
                })

            if release_comparison:
                df_comparison = pd.DataFrame(release_comparison)

                # Completion rate trend
                fig = px.line(df_comparison, x='Release', y='Completion Rate',
                              title='Completion Rate Across Releases',
                              markers=True)
                st.plotly_chart(fig, use_container_width=True)

                # Release comparison table
                st.subheader("📋 Release Comparison")
                st.dataframe(df_comparison, use_container_width=True)

    except Exception as e:
        st.error(f"Error loading analytics: {str(e)}")

def show_configuration_settings():
    """Display configuration settings"""

    st.subheader("⚙️ Application Configuration")

    # Application settings
    st.markdown("### 🚀 Application Settings")

    col1, col2 = st.columns(2)

    with col1:
        st.info(f"**App Name:** {APP_CONFIG['app_name']}")
        st.info(f"**Version:** {APP_CONFIG['version']}")
        st.info(f"**Release Format:** {APP_CONFIG['release_format']}")

    with col2:
        # Environment info
        st.info(f"**Python Version:** {os.sys.version.split()[0]}")
        st.info(f"**Database Path:** {DATABASE_CONFIG['db_path']}")

    # JIRA configuration
    st.markdown("---")
    st.markdown("### 🔗 JIRA Integration")

    jira_configured = bool(JIRA_CONFIG['server_url'] and
                           JIRA_CONFIG['username'] and
                           JIRA_CONFIG['api_token'])

    status_icon = "✅" if jira_configured else "⚠️"
    st.markdown(f"{status_icon} **JIRA Status:** {'Configured' if jira_configured else 'Not Configured'}")

    if jira_configured:
        st.success(f"Connected to: {JIRA_CONFIG['server_url']}")
        st.info(f"Project Key: {JIRA_CONFIG['project_key']}")
    else:
        st.warning("JIRA integration is not configured. Using mock data.")
        st.info("Configure JIRA credentials in the .env file to enable real integration.")

    # Workflow conventions
    st.markdown("---")
    st.markdown("### 📋 Workflow Conventions")

    with st.expander("View Workflow Rules"):
        st.json(WORKFLOW_CONVENTIONS)

    # Allow editing workflow rules
    st.markdown("#### Edit Required Fields")

    for status, fields in WORKFLOW_CONVENTIONS["required_fields"].items():
        new_fields = st.text_input(
            f"Required fields for '{status}':",
            value=", ".join(fields),
            key=f"fields_{status}"
        )
        # Note: In a real application, you'd save these changes

def show_data_management(db_manager):
    """Display data management tools"""

    st.subheader("📁 Data Management")

    # Database statistics
    st.markdown("### 📊 Database Statistics")

    try:
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()

            # Get table statistics
            tables = [
                'releases', 'jira_tickets', 'weekly_snapshots',
                'notifications', 'personal_notes', 'convention_violations'
            ]

            table_stats = []
            for table in tables:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                table_stats.append({'Table': table.replace('_', ' ').title(), 'Records': count})

            df_stats = pd.DataFrame(table_stats)

            # Display as metrics
            cols = st.columns(3)
            for i, (_, row) in enumerate(df_stats.iterrows()):
                with cols[i % 3]:
                    st.metric(row['Table'], row['Records'])

    except Exception as e:
        st.error(f"Error loading database statistics: {str(e)}")

    # Data export options
    st.markdown("---")
    st.markdown("### 📥 Data Export")

    current_release_id = st.session_state.get('current_release', {}).get('id', 'week2025.30')

    # Get data for export
    try:
        current_tickets = db_manager.get_tickets_for_release(current_release_id)
        current_stats = generate_dashboard_summary(current_tickets, current_release_id)
        notifications = db_manager.get_notifications(current_release_id, show_read=True)

        export_data = {
            'release_id': current_release_id,
            'tickets': current_tickets,
            'statistics': current_stats,
            'notifications': notifications,
            'report_data': True
        }

        create_export_buttons(export_data, f"release_{current_release_id}")

    except Exception as e:
        st.error(f"Error preparing export data: {str(e)}")

    # Database maintenance
    st.markdown("---")
    st.markdown("### 🔧 Database Maintenance")

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("🧹 Cleanup Old Data"):
            # This would trigger the cleanup process
            st.info("Data cleanup would be performed here")

    with col2:
        if st.button("📊 Rebuild Statistics"):
            st.info("Database statistics would be rebuilt here")

    with col3:
        if st.button("💾 Create Backup"):
            st.info("Database backup would be created here")

def show_advanced_settings(db_manager):
    """Display advanced settings and tools"""

    st.subheader("🚀 Advanced Settings")

    # Scheduler management
    st.markdown("### ⏰ Scheduler Management")

    scheduler = get_scheduler()
    scheduler_status = scheduler.get_scheduler_status()

    status_icon = "🟢" if scheduler_status['running'] else "🔴"
    st.markdown(f"{status_icon} **Scheduler Status:** {'Running' if scheduler_status['running'] else 'Stopped'}")

    # Scheduler controls
    col1, col2 = st.columns(2)

    with col1:
        if not scheduler_status['running']:
            if st.button("▶️ Start Scheduler"):
                scheduler.start()
                st.success("Scheduler started!")
                st.rerun()

    with col2:
        if scheduler_status['running']:
            if st.button("⏹️ Stop Scheduler"):
                scheduler.stop()
                st.success("Scheduler stopped!")
                st.rerun()

    # Scheduled jobs information
    if scheduler_status['jobs']:
        st.markdown("#### 📋 Scheduled Jobs")
        jobs_df = pd.DataFrame(scheduler_status['jobs'])
        st.dataframe(jobs_df, use_container_width=True)

    # Manual operations
    st.markdown("---")
    st.markdown("### 🔧 Manual Operations")

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("📸 Create Snapshot"):
            current_release_id = st.session_state.get('current_release', {}).get('id')
            if current_release_id:
                # Manual snapshot creation
                from services.jira_service import JiraService
                jira_service = JiraService()
                tickets = jira_service.get_tickets_for_release(current_release_id)

                if db_manager.create_weekly_snapshot(current_release_id, tickets):
                    st.success("Snapshot created successfully!")
                else:
                    st.error("Failed to create snapshot")
            else:
                st.error("No current release selected")

    with col2:
        if st.button("🔄 Sync JIRA Data"):
            st.info("JIRA synchronization would be performed here")

    with col3:
        if st.button("🔔 Generate Notifications"):
            st.info("Notification generation would be triggered here")

    # System logs
    st.markdown("---")
    st.markdown("### 📝 System Logs")

    if st.button("📋 View Recent Logs"):
        # This would display recent log entries
        st.info("Recent system logs would be displayed here")

        # Mock log entries
        sample_logs = [
            "2025-07-22 10:30:15 [INFO] Dashboard refreshed by user",
            "2025-07-22 10:25:10 [INFO] Weekly snapshot created for week2025.30",
            "2025-07-22 09:45:02 [INFO] JIRA data synchronized",
            "2025-07-22 09:00:01 [INFO] System health check completed",
        ]

        for log_entry in sample_logs:
            st.text(log_entry)

    # Debug information
    st.markdown("---")
    st.markdown("### 🐛 Debug Information")

    if st.checkbox("Show Session State"):
        st.json(dict(st.session_state))

    if st.checkbox("Show Configuration"):
        debug_config = {
            'APP_CONFIG': APP_CONFIG,
            'JIRA_CONFIG': {k: v if k != 'api_token' else '***' for k, v in JIRA_CONFIG.items()},
            'DATABASE_CONFIG': DATABASE_CONFIG
        }
        st.json(debug_config)