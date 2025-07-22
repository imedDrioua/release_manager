"""
Notifications Page for Release Management Application
File: pages/notifications.py
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import json

from services.jira_service import JiraService
from utils.session_state import get_current_release_id

def show_notifications(db_manager):
    """Display the notifications page"""

    st.title("🔔 Release Notifications")

    current_release_id = get_current_release_id()

    # Header controls
    col1, col2, col3 = st.columns([2, 1, 1])

    with col1:
        st.subheader(f"Changes for Release: {current_release_id}")

    with col2:
        show_read = st.checkbox("Show Read Notifications")

    with col3:
        if st.button("🔄 Check for Updates", type="primary"):
            check_for_new_changes(db_manager, current_release_id)
            st.success("Checked for updates!")
            st.rerun()

    # Compare with last snapshot and generate notifications
    generate_notifications_from_comparison(db_manager, current_release_id)

    # Display notifications
    display_notifications(db_manager, current_release_id, show_read)

    # Show snapshot information
    show_snapshot_info(db_manager, current_release_id)

def check_for_new_changes(db_manager, release_id):
    """Check for new changes by comparing with last snapshot"""
    try:
        # Get current tickets
        jira_service = JiraService()
        current_tickets = jira_service.get_tickets_for_release(release_id)

        # Store current tickets in database
        for ticket in current_tickets:
            ticket_data = {
                'key': ticket['key'],
                'release_id': release_id,
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
            db_manager.upsert_jira_ticket(ticket_data)

        # Generate notifications by comparing with last snapshot
        generate_notifications_from_comparison(db_manager, release_id)

    except Exception as e:
        st.error(f"Error checking for changes: {str(e)}")

def generate_notifications_from_comparison(db_manager, release_id):
    """Generate notifications by comparing current state with last snapshot"""
    try:
        # Get last snapshot
        last_snapshot = db_manager.get_last_snapshot(release_id)
        if not last_snapshot:
            st.info("No previous snapshot found. Creating baseline for future comparisons.")
            # Create initial snapshot
            current_tickets = db_manager.get_tickets_for_release(release_id)
            db_manager.create_weekly_snapshot(release_id, current_tickets)
            return

        # Get current tickets
        current_tickets = db_manager.get_tickets_for_release(release_id)
        previous_tickets = last_snapshot['ticket_data']

        # Create lookup dictionaries
        current_lookup = {t['key']: t for t in current_tickets}
        previous_lookup = {t['key']: t for t in previous_tickets}

        notifications_created = 0

        # Find new tickets
        for ticket_key in current_lookup:
            if ticket_key not in previous_lookup:
                db_manager.create_notification(
                    ticket_key=ticket_key,
                    release_id=release_id,
                    notification_type='new_ticket',
                    title=f'New Ticket Added',
                    message=f'New ticket {ticket_key} was added to the release',
                    metadata={'ticket_summary': current_lookup[ticket_key]['summary']}
                )
                notifications_created += 1

        # Find removed tickets
        for ticket_key in previous_lookup:
            if ticket_key not in current_lookup:
                db_manager.create_notification(
                    ticket_key=ticket_key,
                    release_id=release_id,
                    notification_type='removed_ticket',
                    title=f'Ticket Removed',
                    message=f'Ticket {ticket_key} was removed from the release',
                    metadata={'ticket_summary': previous_lookup[ticket_key]['summary']}
                )
                notifications_created += 1

        # Find changed tickets
        for ticket_key in current_lookup:
            if ticket_key in previous_lookup:
                current_ticket = current_lookup[ticket_key]
                previous_ticket = previous_lookup[ticket_key]

                # Check for field changes
                changes = compare_tickets(previous_ticket, current_ticket)

                for change in changes:
                    db_manager.create_notification(
                        ticket_key=ticket_key,
                        release_id=release_id,
                        notification_type='field_changed',
                        title=f'{change["field"].title()} Changed',
                        message=f'{ticket_key}: {change["field"]} changed from "{change["old_value"]}" to "{change["new_value"]}"',
                        metadata={
                            'field': change['field'],
                            'old_value': change['old_value'],
                            'new_value': change['new_value'],
                            'ticket_summary': current_ticket['summary']
                        }
                    )
                    notifications_created += 1

        if notifications_created > 0:
            st.session_state.notifications_generated = notifications_created

    except Exception as e:
        st.error(f"Error generating notifications: {str(e)}")

def compare_tickets(previous_ticket, current_ticket):
    """Compare two ticket versions and return list of changes"""
    changes = []

    # Fields to monitor for changes
    fields_to_check = ['status', 'assignee', 'priority', 'summary']

    for field in fields_to_check:
        old_value = previous_ticket.get(field)
        new_value = current_ticket.get(field)

        # Handle None values
        old_value = old_value if old_value is not None else 'None'
        new_value = new_value if new_value is not None else 'None'

        if str(old_value) != str(new_value):
            changes.append({
                'field': field,
                'old_value': old_value,
                'new_value': new_value
            })

    return changes

def display_notifications(db_manager, release_id, show_read):
    """Display notifications with filtering and actions"""
    try:
        notifications = db_manager.get_notifications(release_id, show_read)

        if not notifications:
            st.info("No notifications to display.")
            return

        st.subheader(f"📬 {len(notifications)} Notification(s)")

        # Filter options
        col1, col2 = st.columns(2)
        with col1:
            notification_types = list(set(n['notification_type'] for n in notifications))
            type_filter = st.selectbox("Filter by Type:", ["All"] + notification_types)

        with col2:
            if st.button("Mark All as Read"):
                for notification in notifications:
                    if not notification['is_read']:
                        db_manager.mark_notification_read(notification['id'])
                st.success("All notifications marked as read!")
                st.rerun()

        # Filter notifications
        filtered_notifications = notifications
        if type_filter != "All":
            filtered_notifications = [n for n in notifications if n['notification_type'] == type_filter]

        # Display notifications
        for notification in filtered_notifications:
            display_notification_card(db_manager, notification)

    except Exception as e:
        st.error(f"Error displaying notifications: {str(e)}")

def display_notification_card(db_manager, notification):
    """Display a single notification card"""
    # Determine notification icon and color based on type
    icon_map = {
        'new_ticket': '🆕',
        'removed_ticket': '🗑️',
        'field_changed': '✏️',
        'status_changed': '📊',
        'assignee_changed': '👤'
    }

    color_map = {
        'new_ticket': '#d4edda',
        'removed_ticket': '#f8d7da',
        'field_changed': '#fff3cd',
        'status_changed': '#cce5ff',
        'assignee_changed': '#e7f3ff'
    }

    icon = icon_map.get(notification['notification_type'], '📝')
    bg_color = color_map.get(notification['notification_type'], '#f8f9fa')

    # Read/Unread styling
    border_style = "border-left: 4px solid #007bff;" if not notification['is_read'] else "border-left: 4px solid #6c757d;"
    opacity = "opacity: 0.7;" if notification['is_read'] else ""

    with st.container():
        st.markdown(f"""
        <div style="
            background-color: {bg_color};
            {border_style}
            {opacity}
            padding: 1rem;
            margin: 0.5rem 0;
            border-radius: 5px;
        ">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <h4 style="margin: 0; color: #333;">
                        {icon} {notification['title']}
                    </h4>
                    <p style="margin: 0.5rem 0; color: #666;">
                        <strong>Ticket:</strong> {notification['ticket_key']}
                    </p>
                    <p style="margin: 0.5rem 0; color: #666;">
                        {notification['message']}
                    </p>
                    <small style="color: #888;">
                        {notification['created_at']}
                    </small>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Action buttons
        col1, col2, col3 = st.columns([1, 1, 8])

        with col1:
            if not notification['is_read']:
                if st.button("✓", key=f"mark_read_{notification['id']}",
                             help="Mark as read", type="secondary"):
                    db_manager.mark_notification_read(notification['id'])
                    st.rerun()

        with col2:
            # Show metadata if available
            if notification['metadata']:
                with st.expander("Details", expanded=False):
                    metadata = notification['metadata']
                    if isinstance(metadata, dict):
                        for key, value in metadata.items():
                            st.write(f"**{key.title()}:** {value}")
                    else:
                        st.write(metadata)

def show_snapshot_info(db_manager, release_id):
    """Show information about snapshots"""
    st.markdown("---")
    st.subheader("📸 Snapshot Information")

    try:
        last_snapshot = db_manager.get_last_snapshot(release_id)

        if last_snapshot:
            col1, col2, col3 = st.columns(3)

            with col1:
                st.metric("Last Snapshot", last_snapshot['snapshot_date'][:10])

            with col2:
                ticket_count = len(last_snapshot['ticket_data'])
                st.metric("Tickets in Snapshot", ticket_count)

            with col3:
                # Calculate days since last snapshot
                snapshot_date = datetime.fromisoformat(last_snapshot['snapshot_date'].replace('Z', ''))
                days_ago = (datetime.now() - snapshot_date).days
                st.metric("Days Since Snapshot", days_ago)

            # Manual snapshot creation
            if st.button("📸 Create Snapshot Now"):
                current_tickets = db_manager.get_tickets_for_release(release_id)
                if db_manager.create_weekly_snapshot(release_id, current_tickets):
                    st.success("Snapshot created successfully!")
                    st.rerun()
                else:
                    st.error("Failed to create snapshot.")
        else:
            st.info("No snapshots available for this release.")

            # Create initial snapshot
            if st.button("Create Initial Snapshot"):
                current_tickets = db_manager.get_tickets_for_release(release_id)
                if db_manager.create_weekly_snapshot(release_id, current_tickets):
                    st.success("Initial snapshot created!")
                    st.rerun()
                else:
                    st.error("Failed to create initial snapshot.")

        # Automated snapshot schedule info
        st.info("""
        **Automated Snapshots:** Snapshots are automatically created every Friday at 5:00 PM 
        to track changes over the weekend and provide notifications on Monday morning.
        """)

    except Exception as e:
        st.error(f"Error loading snapshot information: {str(e)}")