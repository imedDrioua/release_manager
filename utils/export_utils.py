"""
Export and reporting utilities for Release Management Application
File: utils/export_utils.py
"""

import json
import csv
import io
from datetime import datetime
from typing import List, Dict, Any
import pandas as pd
import streamlit as st

def export_tickets_to_csv(tickets: List[Dict]) -> str:
    """Export tickets data to CSV format"""

    if not tickets:
        return ""

    # Prepare data for CSV
    csv_data = []
    for ticket in tickets:
        csv_data.append({
            'Ticket Key': ticket.get('key', ''),
            'Summary': ticket.get('summary', ''),
            'Status': ticket.get('status', ''),
            'Priority': ticket.get('priority', ''),
            'Assignee': ticket.get('assignee', 'Unassigned'),
            'Reporter': ticket.get('reporter', ''),
            'Issue Type': ticket.get('issueType', ''),
            'Created Date': ticket.get('created', '')[:10] if ticket.get('created') else '',
            'Updated Date': ticket.get('updated', '')[:10] if ticket.get('updated') else '',
            'Fix Version': ', '.join(ticket.get('fixVersions', [])),
            'Components': ', '.join(ticket.get('components', [])),
            'Labels': ', '.join(ticket.get('labels', []))
        })

    # Convert to CSV
    output = io.StringIO()
    if csv_data:
        fieldnames = csv_data[0].keys()
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(csv_data)

    return output.getvalue()

def export_release_report(release_id: str, tickets: List[Dict],
                          statistics: Dict, notes: List[Dict] = None) -> str:
    """Generate comprehensive release report"""

    report = f"""
RELEASE REPORT - {release_id}
Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
======================================================================

RELEASE OVERVIEW
----------------
Release ID: {release_id}
Total Tickets: {statistics.get('total', 0)}
Completed Tickets: {statistics.get('by_status', {}).get('Done', 0)}
Blocked Tickets: {statistics.get('by_status', {}).get('Blocked', 0)}
In Progress: {statistics.get('by_status', {}).get('In Progress', 0)}

COMPLETION RATE
---------------
"""

    total = statistics.get('total', 0)
    done = statistics.get('by_status', {}).get('Done', 0)
    completion_rate = round((done / total * 100) if total > 0 else 0, 1)

    report += f"Progress: {completion_rate}% ({done}/{total} tickets completed)\n\n"

    # Status breakdown
    report += "STATUS BREAKDOWN\n"
    report += "----------------\n"
    status_stats = statistics.get('by_status', {})
    for status, count in status_stats.items():
        percentage = round((count / total * 100) if total > 0 else 0, 1)
        report += f"{status}: {count} ({percentage}%)\n"

    report += "\n"

    # Priority breakdown
    report += "PRIORITY BREAKDOWN\n"
    report += "------------------\n"
    priority_stats = statistics.get('by_priority', {})
    for priority, count in priority_stats.items():
        percentage = round((count / total * 100) if total > 0 else 0, 1)
        report += f"{priority}: {count} ({percentage}%)\n"

    report += "\n"

    # High priority tickets details
    high_priority_tickets = [t for t in tickets if t.get('priority') in ['High', 'Highest']]
    if high_priority_tickets:
        report += "HIGH PRIORITY TICKETS\n"
        report += "---------------------\n"
        for ticket in high_priority_tickets:
            report += f"{ticket['key']}: {ticket['summary']} [{ticket['status']}]\n"
        report += "\n"

    # Blocked tickets details
    blocked_tickets = [t for t in tickets if t.get('status') == 'Blocked']
    if blocked_tickets:
        report += "BLOCKED TICKETS\n"
        report += "---------------\n"
        for ticket in blocked_tickets:
            report += f"{ticket['key']}: {ticket['summary']} [Assignee: {ticket.get('assignee', 'Unassigned')}]\n"
        report += "\n"

    # Unassigned tickets
    unassigned_tickets = [t for t in tickets if not t.get('assignee')]
    if unassigned_tickets:
        report += "UNASSIGNED TICKETS\n"
        report += "------------------\n"
        for ticket in unassigned_tickets:
            report += f"{ticket['key']}: {ticket['summary']} [{ticket['status']}]\n"
        report += "\n"

    # Team workload
    assignee_counts = {}
    for ticket in tickets:
        assignee = ticket.get('assignee', 'Unassigned')
        assignee_counts[assignee] = assignee_counts.get(assignee, 0) + 1

    if assignee_counts:
        report += "TEAM WORKLOAD\n"
        report += "-------------\n"
        for assignee, count in sorted(assignee_counts.items(), key=lambda x: x[1], reverse=True):
            percentage = round((count / total * 100) if total > 0 else 0, 1)
            report += f"{assignee}: {count} tickets ({percentage}%)\n"
        report += "\n"

    # Release notes if provided
    if notes:
        report += "RELEASE NOTES\n"
        report += "-------------\n"
        for note in notes:
            report += f"• {note.get('title', 'Untitled')}\n"
            content_preview = note.get('content', '')[:100]
            if len(note.get('content', '')) > 100:
                content_preview += "..."
            report += f"  {content_preview}\n\n"

    report += "======================================================================\n"
    report += f"Report generated by Release Management System v1.0.0\n"

    return report

def export_notifications_to_json(notifications: List[Dict]) -> str:
    """Export notifications to JSON format"""

    # Clean up notifications for export
    export_data = []
    for notification in notifications:
        export_data.append({
            'ticket_key': notification['ticket_key'],
            'notification_type': notification['notification_type'],
            'title': notification['title'],
            'message': notification['message'],
            'created_at': notification['created_at'],
            'is_read': notification['is_read'],
            'metadata': notification.get('metadata', {})
        })

    return json.dumps(export_data, indent=2, default=str)

def create_export_buttons(data_dict: Dict[str, Any], filename_prefix: str = "export"):
    """Create export buttons for different formats"""

    st.subheader("📥 Export Data")

    col1, col2, col3 = st.columns(3)

    with col1:
        if 'tickets' in data_dict and st.button("📊 Export CSV"):
            csv_data = export_tickets_to_csv(data_dict['tickets'])
            if csv_data:
                st.download_button(
                    label="Download CSV",
                    data=csv_data,
                    file_name=f"{filename_prefix}_tickets_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )

    with col2:
        if 'report_data' in data_dict and st.button("📋 Export Report"):
            report = export_release_report(
                data_dict['release_id'],
                data_dict['tickets'],
                data_dict['statistics'],
                data_dict.get('notes', [])
            )
            st.download_button(
                label="Download Report",
                data=report,
                file_name=f"{filename_prefix}_report_{datetime.now().strftime('%Y%m%d')}.txt",
                mime="text/plain"
            )

    with col3:
        if 'notifications' in data_dict and st.button("🔔 Export JSON"):
            json_data = export_notifications_to_json(data_dict['notifications'])
            st.download_button(
                label="Download JSON",
                data=json_data,
                file_name=f"{filename_prefix}_notifications_{datetime.now().strftime('%Y%m%d')}.json",
                mime="application/json"
            )

def generate_dashboard_summary(tickets: List[Dict], release_id: str) -> Dict:
    """Generate dashboard summary statistics"""

    if not tickets:
        return {'total': 0, 'by_status': {}, 'by_priority': {}}

    # Basic stats
    total = len(tickets)

    # Group by status
    status_counts = {}
    for ticket in tickets:
        status = ticket.get('status', 'Unknown')
        status_counts[status] = status_counts.get(status, 0) + 1

    # Group by priority
    priority_counts = {}
    for ticket in tickets:
        priority = ticket.get('priority', 'Unknown')
        priority_counts[priority] = priority_counts.get(priority, 0) + 1

    # Group by assignee
    assignee_counts = {}
    for ticket in tickets:
        assignee = ticket.get('assignee', 'Unassigned')
        assignee_counts[assignee] = assignee_counts.get(assignee, 0) + 1

    # Additional metrics
    high_priority_count = len([t for t in tickets if t.get('priority') in ['High', 'Highest']])
    blocked_count = status_counts.get('Blocked', 0)
    done_count = status_counts.get('Done', 0)
    unassigned_count = assignee_counts.get('Unassigned', 0)

    return {
        'total': total,
        'by_status': status_counts,
        'by_priority': priority_counts,
        'by_assignee': assignee_counts,
        'high_priority': high_priority_count,
        'blocked': blocked_count,
        'completed': done_count,
        'unassigned': unassigned_count,
        'completion_rate': round((done_count / total * 100) if total > 0 else 0, 1)
    }

def format_duration(seconds: int) -> str:
    """Format duration in seconds to human readable format"""

    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        minutes = seconds // 60
        return f"{minutes}m"
    elif seconds < 86400:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours}h {minutes}m"
    else:
        days = seconds // 86400
        hours = (seconds % 86400) // 3600
        return f"{days}d {hours}h"