def search_issues_by_user(self, username: str, role: str, max_results: int = 500) -> List[Dict[str, Any]]:
    """Recherche des tickets par utilisateur et rôle."""
    jql = f'{role} = "{username}" ORDER BY created DESC'
    fields = self.fields if hasattr(self, 'fields') else [
        'summary', 'status', 'components', 'assignee', 'reporter', 
        'updated', 'created', 'priority', 'description', 'resolution', 
        'resolutiondate', 'timeoriginalestimate', 'timespent'
    ]
    return self.search_issues(jql, fields, max_results)



def search_issues_by_user(self, username: str, role: str, max_results: int = 500) -> List[Dict[str, Any]]:
    """Retourne des données factices pour un utilisateur."""
    # Générer des données factices variées pour l'analyse
    import random
    from datetime import datetime, timedelta
    
    mock_issues = []
    statuses = ['To Do', 'In Progress', 'Done', 'delivery done', 'pushed to master git', 
                'homologation done', 'no git involved']
    priorities = ['Critical', 'High', 'Medium', 'Low']
    components = ['Frontend', 'Backend', 'Database', 'API', 'Infrastructure']
    
    # Générer 50-150 tickets sur les 6 derniers mois
    num_tickets = random.randint(50, 150)
    
    for i in range(num_tickets):
        created_date = datetime.now() - timedelta(days=random.randint(1, 180))
        status = random.choice(statuses)
        
        # Si le ticket est terminé, ajouter une date de résolution
        resolution_date = None
        if status in ['Done', 'delivery done', 'pushed to master git', 'no git involved']:
            resolution_date = created_date + timedelta(days=random.randint(1, 30))
        
        issue = {
            'key': f'PROJ-{1000 + i}',
            'id': str(1000 + i),
            'fields': {
                'summary': f'Ticket exemple {i+1} pour {username}',
                'status': status,
                'components': random.sample(components, k=random.randint(1, 3)),
                'assignee': username if role == 'assignee' else random.choice(['John Doe', 'Jane Smith']),
                'reporter': username if role == 'reporter' else random.choice(['Alice Brown', 'Bob Wilson']),
                'priority': random.choice(priorities),
                'created': created_date.isoformat(),
                'updated': (created_date + timedelta(days=random.randint(0, 10))).isoformat(),
                'description': f'Description du ticket {i+1}',
                'resolution': 'Fixed' if resolution_date else None,
                'resolutiondate': resolution_date.isoformat() if resolution_date else None
            },
            'changelog': []
        }
        
        # Ajouter un historique pour les tickets avec homologation
        if random.random() > 0.7 and status in ['Done', 'delivery done']:
            homolog_date = created_date + timedelta(days=random.randint(5, 25))
            issue['changelog'].append({
                'field': 'status',
                'from': 'In Progress',
                'to': 'homologation done',
                'author': 'System',
                'created': homolog_date.isoformat()
            })
        
        mock_issues.append(issue)
    
    return mock_issues



page = st.radio(
    "Aller à",
    ["📊 Dashboard", "🔔 Notifications", "📝 Notes personnelles"],
    label_visibility="collapsed"
)To:page = st.radio(
    "Aller à",
    ["📊 Dashboard", "🔔 Notifications", "📝 Notes personnelles", "👤 Analyse utilisateur"],
    label_visibility="collapsed"
)5. In the same file main.py, add the import at the top:from pages.user_analytics import render_user_analytics6. In the main() function of main.py, add the new page handling:After the existing page conditions, add:elif selected_page == "👤 Analyse utilisateur":
    render_user_analytics(jira_client)