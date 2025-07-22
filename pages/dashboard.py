"""
Dashboard Page for Release Management Application
File: pages/dashboard.py
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
import json

from services.jira_service import JiraService
from utils.session_state import (
    get_current_release_id, get_selected_ticket, set_selected_ticket,
    mark_dashboard_refreshed, get_last_refresh, update_tickets_data, get_tickets_data
)
from config.settings import UI_CONFIG

def show_dashboard(db_manager):
    """Display the dashboard page"""

    st.title("📊 Release Dashboard")

    current_release_id = get_current_release_id()

    # Header with refresh button
    col1, col2, col3 = st.columns([2, 1, 1])

    with col1:
        st.subheader(f"Release: {current_release_id}")
        last_refresh = get_last_refresh()
        if last_refresh:
            st.caption(f"Last refreshed: {last_refresh.strftime('%Y-%m-%d %H:%M:%S')}")

    with col3:
        if st.button("🔄 Refresh Data", type="primary"):
            refresh_dashboard_data(db_manager, current_release_id)
            st.success("Data refreshed successfully!")
            st.rerun()

    # Initialize JIRA service
    jira_service = JiraService()

    # Get tickets data
    tickets_data = get_tickets_data()
    if not tickets_data:
        with st.spinner("Loading tickets data..."):
            tickets_data = fetch_and_store_tickets(db_manager, jira_service, current_release_id)

    if not tickets_data:
        st.warning("No tickets found for this release.")
        return

    # Display statistics
    show_release_statistics(tickets_data)

    st.markdown("---")

    # Main content in two columns
    col1, col2 = st.columns([2, 1])

    with col1:
        show_tickets_table(tickets_data)

    with col2:
        show_workflow_violations(jira_service, tickets_data)

    st.markdown("---")

    # Ticket history section
    show_ticket_history_section(jira_service, tickets_data)

def refresh_dashboard_data(db_manager, release_id):
    """Refresh dashboard data"""
    jira_service = JiraService()
    jira_service.refresh_ticket_data(release_id)
    fetch_and_store_tickets(db_manager, jira_service, release_id)
    mark_dashboard_refreshed()

def fetch_and_store_tickets(db_manager, jira_service, release_id):
    """Fetch tickets from JIRA and store in database"""
    try:
        # Fetch tickets from JIRA
        tickets = jira_service.get_tickets_for_release(release_id)

        # Store in database
        for ticket in tickets:
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

        # Update session state
        update_tickets_data(tickets)

        return tickets
    except Exception as e:
        st.error(f"Error fetching tickets: {str(e)}")
        return []

def show_release_statistics(tickets_data):
    """Display release statistics with charts"""
    if not tickets_data:
        return

    st.subheader("📈 Release Statistics")

    # Convert to DataFrame for easier analysis
    df = pd.DataFrame(tickets_data)

    # Key metrics in columns
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        total_tickets = len(tickets_data)
        st.metric("Total Tickets", total_tickets)

    with col2:
        done_tickets = len(df[df['status'] == 'Done'])
        progress = round((done_tickets / total_tickets * 100) if total_tickets > 0 else 0, 1)
        st.metric("Completed", f"{done_tickets}", f"{progress}%")

    with col3:
        blocked_tickets = len(df[df['status'] == 'Blocked'])
        st.metric("Blocked", blocked_tickets, delta_color="inverse")

    with col4:
        high_priority = len(df[df['priority'].isin(['High', 'Highest'])])
        st.metric("High Priority", high_priority)

    with col5:
        unassigned = len(df[df['assignee'].isna()])
        st.metric("Unassigned", unassigned, delta_color="inverse")

    # Charts
    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        # Status distribution pie chart
        status_counts = df['status'].value_counts()
        fig_status = px.pie(
            values=status_counts.values,
            names=status_counts.index,
            title="Tickets by Status",
            color_discrete_map=UI_CONFIG["status_colors"]
        )
        fig_status.update_layout(height=400)
        st.plotly_chart(fig_status, use_container_width=True)

    with chart_col2:
        # Priority distribution bar chart
        priority_order = ['Lowest', 'Low', 'Medium', 'High', 'Highest']
        priority_counts = df['priority'].value_counts().reindex(priority_order, fill_value=0)

        fig_priority = px.bar(
            x=priority_counts.index,
            y=priority_counts.values,
            title="Tickets by Priority",
            labels={'x': 'Priority', 'y': 'Count'},
            color=priority_counts.values,
            color_continuous_scale='RdYlBu_r'
        )
        fig_priority.update_layout(height=400, showlegend=False)
        st.plotly_chart(fig_priority, use_container_width=True)

    # Assignee workload
    if not df['assignee'].isna().all():
        st.subheader("👥 Team Workload")
        assignee_counts = df['assignee'].value_counts().head(10)

        fig_assignee = px.bar(
            x=assignee_counts.values,
            y=assignee_counts.index,
            orientation='h',
            title="Tickets by Assignee",
            labels={'x': 'Number of Tickets', 'y': 'Assignee'}
        )
        fig_assignee.update_layout(height=400)
        st.plotly_chart(fig_assignee, use_container_width=True)

def show_tickets_table(tickets_data):
    """Display tickets in a table with filtering"""
    st.subheader("🎫 Release Tickets")

    if not tickets_data:
        st.info("No tickets to display")
        return

    # Filters
    col1, col2, col3 = st.columns(3)

    with col1:
        status_filter = st.selectbox(
            "Filter by Status:",
            ["All"] + list(set(ticket['status'] for ticket in tickets_data))
        )

    with col2:
        priority_filter = st.selectbox(
            "Filter by Priority:",
            ["All"] + list(set(ticket['priority'] for ticket in tickets_data))
        )

    with col3:
        assignee_filter = st.selectbox(
            "Filter by Assignee:",
            ["All"] + list(set(ticket.get('assignee', 'Unassigned') for ticket in tickets_data if ticket.get('assignee')))
        )

    # Apply filters
    filtered_tickets = tickets_data.copy()

    if status_filter != "All":
        filtered_tickets = [t for t in filtered_tickets if t['status'] == status_filter]

    if priority_filter != "All":
        filtered_tickets = [t for t in filtered_tickets if t['priority'] == priority_filter]

    if assignee_filter != "All":
        filtered_tickets = [t for t in filtered_tickets if t.get('assignee') == assignee_filter]

    # Display tickets
    if filtered_tickets:
        for ticket in filtered_tickets[:20]:  # Limit to 20 for performance
            with st.expander(f"{ticket['key']} - {ticket['summary']}", expanded=False):
                ticket_col1, ticket_col2 = st.columns(2)

                with ticket_col1:
                    st.write(f"**Status:** {ticket['status']}")
                    st.write(f"**Priority:** {ticket['priority']}")
                    st.write(f"**Type:** {ticket['issueType']}")
                    st.write(f"**Assignee:** {ticket.get('assignee', 'Unassigned')}")

                with ticket_col2:
                    st.write(f"**Reporter:** {ticket.get('reporter', 'Unknown')}")
                    st.write(f"**Created:** {ticket['created'][:10]}")
                    st.write(f"**Updated:** {ticket['updated'][:10]}")

                    if st.button(f"Select for History", key=f"select_{ticket['key']}"):
                        set_selected_ticket(ticket['key'])
                        st.rerun()

                if ticket.get('labels'):
                    st.write(f"**Labels:** {', '.join(ticket['labels'])}")
    else:
        st.info("No tickets match the current filters.")

def show_workflow_violations(jira_service, tickets_data):
    """Show workflow convention violations"""
    st.subheader("⚠️ Workflow Violations")

    selected_ticket_key = st.selectbox(
        "Select ticket to check:",
        [""] + [ticket['key'] for ticket in tickets_data],
        key="violation_ticket_select"
    )

    if selected_ticket_key:
        # Find the selected ticket
        selected_ticket = next((t for t in tickets_data if t['key'] == selected_ticket_key), None)

        if selected_ticket:
            violations = jira_service.check_workflow_conventions(selected_ticket)

            if violations:
                for violation in violations:
                    severity_color = {
                        'low': '🔵',
                        'medium': '🟡',
                        'high': '🔴'
                    }.get(violation['severity'], '⚪')

                    st.markdown(f"""
                    <div class="warning-box">
                        <strong>{severity_color} {violation['type'].replace('_', ' ').title()}</strong><br>
                        {violation['description']}
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.markdown("""
                <div class="success-box">
                    ✅ <strong>No violations found!</strong><br>
                    This ticket follows all workflow conventions.
                </div>
                """, unsafe_allow_html=True)

def show_ticket_history_section(jira_service, tickets_data):
    """Show ticket field history"""
    st.subheader("📋 Ticket Field History")

    # Ticket and field selection
    col1, col2 = st.columns(2)

    with col1:
        selected_ticket_key = get_selected_ticket()
        if not selected_ticket_key and tickets_data:
            selected_ticket_key = tickets_data[0]['key']

        ticket_key = st.selectbox(
            "Select Ticket:",
            [ticket['key'] for ticket in tickets_data],
            index=0 if selected_ticket_key and selected_ticket_key in [t['key'] for t in tickets_data]
            else 0,
            key="history_ticket_select"
        )

    with col2:
        field = st.selectbox(
            "Select Field:",
            ["status", "assignee", "priority", "fixVersions"],
            key="history_field_select"
        )

    if ticket_key and field:
        # Get field history
        history = jira_service.get_ticket_history(ticket_key, field)

        if history:
            # Create a timeline visualization
            st.subheader(f"📊 {field.title()} Changes for {ticket_key}")

            # Prepare data for timeline
            timeline_data = []
            for change in sorted(history, key=lambda x: x['changed_at']):
                timeline_data.append({
                    'Date': change['changed_at'][:10],
                    'Time': change['changed_at'][11:19],
                    'From': change['old_value'] or 'None',
                    'To': change['new_value'] or 'None',
                    'Changed By': change['changed_by']
                })

            if timeline_data:
                df_history = pd.DataFrame(timeline_data)

                # Display as a nice table
                st.dataframe(df_history, use_container_width=True)

                # Create a flow diagram with Plotly
                fig = go.Figure()

                # Add traces for each change
                for i, change in enumerate(timeline_data):
                    fig.add_trace(go.Scatter(
                        x=[i, i+1],
                        y=[1, 1],
                        mode='lines+markers+text',
                        text=[change['From'], change['To']],
                        textposition="top center",
                        line=dict(color='blue', width=2),
                        marker=dict(size=10),
                        name=f"Change {i+1}",
                        hovertemplate=f"<b>Date:</b> {change['Date']}<br>" +
                                      f"<b>Time:</b> {change['Time']}<br>" +
                                      f"<b>Changed by:</b> {change['Changed By']}<br>" +
                                      f"<b>From:</b> {change['From']}<br>" +
                                      f"<b>To:</b> {change['To']}<extra></extra>"
                    ))

                fig.update_layout(
                    title=f"{field.title()} Change Timeline",
                    xaxis_title="Change Sequence",
                    yaxis_title="",
                    yaxis=dict(showticklabels=False),
                    height=300,
                    showlegend=False
                )

                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info(f"No change history found for {field} in ticket {ticket_key}")