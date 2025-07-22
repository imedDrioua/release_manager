"""
JIRA API Service for Release Management Application
File: services/jira_service.py
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import json
import random

from config.settings import JIRA_CONFIG, JQL_QUERIES, JIRA_FIELDS

class JiraService:
    def __init__(self):
        self.server_url = JIRA_CONFIG["server_url"]
        self.username = JIRA_CONFIG["username"]
        self.api_token = JIRA_CONFIG["api_token"]
        self.project_key = JIRA_CONFIG["project_key"]

        # Mock mode for demo purposes
        self.mock_mode = True

        # Initialize mock data
        self.mock_tickets = self._generate_mock_tickets()

    def _generate_mock_tickets(self) -> List[Dict]:
        """Generate mock JIRA tickets for demo purposes"""
        statuses = ["To Do", "In Progress", "In Review", "Done", "Blocked"]
        priorities = ["Highest", "High", "Medium", "Low", "Lowest"]
        issue_types = ["Story", "Bug", "Task", "Epic"]
        assignees = ["john.doe", "jane.smith", "bob.wilson", "alice.brown", None]

        tickets = []
        for i in range(1, 21):  # Generate 20 mock tickets
            ticket = {
                "key": f"PROJ-{1000 + i}",
                "summary": f"Sample ticket {i} - {random.choice(['Feature', 'Bug fix', 'Enhancement', 'Investigation'])}",
                "status": random.choice(statuses),
                "assignee": random.choice(assignees),
                "priority": random.choice(priorities),
                "issueType": random.choice(issue_types),
                "reporter": random.choice(assignees[:4]),  # Exclude None for reporter
                "created": (datetime.now() - timedelta(days=random.randint(1, 30))).isoformat(),
                "updated": (datetime.now() - timedelta(days=random.randint(0, 7))).isoformat(),
                "fixVersions": ["week2025.30"],
                "components": [random.choice(["Frontend", "Backend", "API", "Database", "Mobile"])],
                "labels": random.sample(["urgent", "technical-debt", "feature", "bugfix", "enhancement"],
                                        random.randint(0, 3)),
                "description": f"This is a sample description for ticket {i}. It contains details about the work to be done.",
                "resolution": "Fixed" if random.choice(statuses) == "Done" else None,
                "worklog": self._generate_mock_worklog(),
                "changelog": self._generate_mock_changelog(i)
            }
            tickets.append(ticket)
        return tickets

    def _generate_mock_worklog(self) -> List[Dict]:
        """Generate mock worklog entries"""
        entries = []
        for _ in range(random.randint(0, 5)):
            entries.append({
                "author": random.choice(["john.doe", "jane.smith", "bob.wilson"]),
                "timeSpent": f"{random.randint(1, 8)}h",
                "comment": "Working on implementation",
                "created": (datetime.now() - timedelta(days=random.randint(1, 10))).isoformat()
            })
        return entries

    def _generate_mock_changelog(self, ticket_num: int) -> List[Dict]:
        """Generate mock changelog entries"""
        changes = []
        statuses = ["To Do", "In Progress", "In Review", "Done"]

        # Generate status changes
        current_status_index = 0
        for i in range(random.randint(1, 4)):
            if current_status_index < len(statuses) - 1:
                old_status = statuses[current_status_index]
                new_status = statuses[current_status_index + 1]
                current_status_index += 1

                changes.append({
                    "field": "status",
                    "old_value": old_status,
                    "new_value": new_status,
                    "changed_by": random.choice(["john.doe", "jane.smith", "bob.wilson"]),
                    "changed_at": (datetime.now() - timedelta(days=random.randint(1, 20))).isoformat()
                })

        # Generate assignee changes
        if random.choice([True, False]):
            changes.append({
                "field": "assignee",
                "old_value": None,
                "new_value": random.choice(["john.doe", "jane.smith"]),
                "changed_by": "project.manager",
                "changed_at": (datetime.now() - timedelta(days=random.randint(1, 15))).isoformat()
            })

        return changes

    def get_tickets_for_release(self, release_id: str) -> List[Dict]:
        """Fetch tickets for a specific release"""
        if self.mock_mode:
            # Filter mock tickets for the release
            filtered_tickets = []
            for ticket in self.mock_tickets:
                if release_id in ticket.get('fixVersions', []):
                    # Add some variation to simulate real-time changes
                    ticket_copy = ticket.copy()
                    if random.random() < 0.1:  # 10% chance of status change
                        statuses = ["To Do", "In Progress", "In Review", "Done", "Blocked"]
                        ticket_copy['status'] = random.choice(statuses)
                        ticket_copy['updated'] = datetime.now().isoformat()
                    filtered_tickets.append(ticket_copy)
            return filtered_tickets
        else:
            # Real JIRA API implementation would go here
            return self._fetch_from_jira_api(release_id)

    def _fetch_from_jira_api(self, release_id: str) -> List[Dict]:
        """Fetch tickets from actual JIRA API"""
        # This would contain the real JIRA API implementation
        # using libraries like jira-python or requests
        try:
            # Example implementation structure:
            # from jira import JIRA
            # jira = JIRA(self.server_url, basic_auth=(self.username, self.api_token))
            # jql = JQL_QUERIES["current_release"].format(release_id=release_id)
            # issues = jira.search_issues(jql, fields=JIRA_FIELDS, maxResults=1000)
            # return [self._format_jira_issue(issue) for issue in issues]
            pass
        except Exception as e:
            logging.error(f"Error fetching from JIRA API: {e}")
            return []

    def _format_jira_issue(self, issue) -> Dict:
        """Format JIRA issue object to standard format"""
        # This would format the actual JIRA issue object
        return {
            "key": issue.key,
            "summary": issue.fields.summary,
            "status": issue.fields.status.name,
            "assignee": issue.fields.assignee.name if issue.fields.assignee else None,
            "priority": issue.fields.priority.name if issue.fields.priority else None,
            "issueType": issue.fields.issuetype.name,
            "reporter": issue.fields.reporter.name if issue.fields.reporter else None,
            "created": issue.fields.created,
            "updated": issue.fields.updated,
            "fixVersions": [v.name for v in issue.fields.fixVersions] if issue.fields.fixVersions else [],
            "components": [c.name for c in issue.fields.components] if issue.fields.components else [],
            "labels": issue.fields.labels or [],
            "description": issue.fields.description or "",
            "resolution": issue.fields.resolution.name if issue.fields.resolution else None,
        }

    def get_ticket_history(self, ticket_key: str, field: str) -> List[Dict]:
        """Get history of changes for a specific field of a ticket"""
        if self.mock_mode:
            # Find the ticket and return its changelog for the specific field
            for ticket in self.mock_tickets:
                if ticket['key'] == ticket_key:
                    changelog = ticket.get('changelog', [])
                    return [change for change in changelog if change['field'] == field]
            return []
        else:
            # Real implementation would fetch from JIRA API
            return self._fetch_ticket_history_from_api(ticket_key, field)

    def _fetch_ticket_history_from_api(self, ticket_key: str, field: str) -> List[Dict]:
        """Fetch ticket history from JIRA API"""
        # Real implementation would go here
        return []

    def check_workflow_conventions(self, ticket: Dict) -> List[Dict]:
        """Check if ticket follows workflow conventions"""
        violations = []

        # Check required fields based on status
        from config.settings import WORKFLOW_CONVENTIONS
        required_fields = WORKFLOW_CONVENTIONS["required_fields"].get(ticket["status"], [])

        for field in required_fields:
            if not ticket.get(field):
                violations.append({
                    "type": "missing_required_field",
                    "severity": "medium",
                    "description": f"Missing required field '{field}' for status '{ticket['status']}'",
                    "field": field
                })

        # Check time limits
        if ticket["status"] in WORKFLOW_CONVENTIONS["time_limits"]:
            max_days = WORKFLOW_CONVENTIONS["time_limits"][ticket["status"]]
            updated_date = datetime.fromisoformat(ticket["updated"].replace('Z', '+00:00'))
            days_in_status = (datetime.now() - updated_date.replace(tzinfo=None)).days

            if days_in_status > max_days:
                violations.append({
                    "type": "time_limit_exceeded",
                    "severity": "high",
                    "description": f"Ticket has been in '{ticket['status']}' for {days_in_status} days (limit: {max_days})",
                    "field": "status",
                    "days_exceeded": days_in_status - max_days
                })

        # Check valid status transitions (if we have previous status)
        # This would require historical data to implement properly

        return violations

    def refresh_ticket_data(self, release_id: str) -> bool:
        """Refresh ticket data from JIRA"""
        try:
            # In mock mode, just simulate a refresh
            if self.mock_mode:
                # Add some random updates to simulate changes
                for ticket in self.mock_tickets:
                    if random.random() < 0.05:  # 5% chance of update
                        ticket['updated'] = datetime.now().isoformat()
                        if random.random() < 0.5:  # 50% chance of status change
                            statuses = ["To Do", "In Progress", "In Review", "Done", "Blocked"]
                            ticket['status'] = random.choice(statuses)
                return True
            else:
                # Real implementation would refresh from JIRA API
                return True
        except Exception as e:
            logging.error(f"Error refreshing ticket data: {e}")
            return False