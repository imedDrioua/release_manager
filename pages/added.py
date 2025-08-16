2. Update api/jira_client.py - Add Agile API methods to JiraClient:# Add these methods to the JiraClient class:

def get_board_sprints(self, board_id: str, max_results: int = 50) -> List[Dict[str, Any]]:
    """Récupère la liste des sprints d'un board."""
    try:
        # Récupérer les sprints (actifs et fermés récents)
        sprints = []
        start_at = 0
        
        while True:
            response = self.jira._session.get(
                f"{self.server}/rest/agile/1.0/board/{board_id}/sprint",
                params={
                    'maxResults': max_results,
                    'startAt': start_at,
                    'state': 'active,closed'
                }
            )
            response.raise_for_status()
            data = response.json()
            
            sprints.extend(data.get('values', []))
            
            if data.get('isLast', True):
                break
            start_at += max_results
        
        # Trier par date de début décroissante (plus récents d'abord)
        sprints.sort(key=lambda x: x.get('startDate', ''), reverse=True)
        
        # Limiter aux 20 derniers sprints
        return sprints[:20]
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des sprints: {e}")
        return []

def get_sprint_issues(self, sprint_id: int, fields: List[str] = None) -> Dict[str, List[Dict[str, Any]]]:
    """Récupère les issues d'un sprint spécifique."""
    try:
        if not fields:
            fields = self.fields if hasattr(self, 'fields') else config.JIRA_FIELDS
        
        # JQL pour les issues du sprint
        jql_current = f"sprint = {sprint_id}"
        jql_completed = f"sprint = {sprint_id} AND status in ('Done', 'Delivery Done', 'Pushed to master git', 'No git involved')"
        jql_incomplete = f"sprint = {sprint_id} AND status not in ('Done', 'Delivery Done', 'Pushed to master git', 'No git involved')"
        
        # Récupérer toutes les issues du sprint
        all_issues = self.search_issues(jql_current, fields, max_results=200)
        
        # Récupérer aussi les issues qui ont été dans ce sprint mais déplacées
        jql_moved = f'"Sprint" was {sprint_id} AND sprint != {sprint_id}'
        moved_issues = self.search_issues(jql_moved, fields, max_results=100)
        
        return {
            'all': all_issues,
            'completed': [i for i in all_issues if i.get('fields', {}).get('status', '').lower() in 
                         ['done', 'delivery done', 'pushed to master git', 'no git involved']],
            'incomplete': [i for i in all_issues if i.get('fields', {}).get('status', '').lower() not in 
                          ['done', 'delivery done', 'pushed to master git', 'no git involved']],
            'moved_out': moved_issues
        }
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des issues du sprint {sprint_id}: {e}")
        return {'all': [], 'completed': [], 'incomplete': [], 'moved_out': []}


4. Update the fetch_and_analyze_sprints function in pages/team_sprint_analysis.py:def fetch_and_analyze_sprints(jira_client: JiraClient):
    """Récupère et analyse toutes les données de sprint via l'API Agile."""
    try:
        # Récupérer le board ID depuis la config
        board_id = config.JIRA_BOARD_ID
        
        with st.spinner("Récupération de la liste des sprints..."):
            # Récupérer la liste des sprints du board
            sprints = jira_client.get_board_sprints(board_id)
            
            if not sprints:
                st.warning("Aucun sprint trouvé pour ce board")
                return
            
            st.info(f"📋 {len(sprints)} sprints trouvés")
        
        # Structure pour stocker toutes les données
        sprint_data = {
            'sprints': {},
            'team_members': {},
            'tickets': [],
            'date_range': {'min': None, 'max': None}
        }
        
        # Progress bar pour le chargement des sprints
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Récupérer les issues pour chaque sprint
        for idx, sprint in enumerate(sprints):
            sprint_id = sprint['id']
            sprint_name = sprint['name']
            
            status_text.text(f"Chargement du sprint {sprint_name}...")
            progress_bar.progress((idx + 1) / len(sprints))
            
            # Récupérer les issues du sprint
            sprint_issues = jira_client.get_sprint_issues(
                sprint_id,
                fields=config.JIRA_FIELDS + ['resolution', 'resolutiondate', 
                                            'timeoriginalestimate', 'timespent', 'sprint']
            )
            
            # Créer l'entrée pour ce sprint
            sprint_data['sprints'][sprint_id] = {
                'id': sprint_id,
                'name': sprint_name,
                'state': sprint.get('state', 'active'),
                'startDate': sprint.get('startDate'),
                'endDate': sprint.get('endDate'),
                'goal': sprint.get('goal', ''),
                'tickets': sprint_issues['all'],
                'completed_tickets': sprint_issues['completed'],
                'incomplete_tickets': sprint_issues['incomplete'],
                'moved_out_tickets': sprint_issues['moved_out'],
                'team_members': set()
            }
            
            # Ajouter tous les tickets à la liste globale
            sprint_data['tickets'].extend(sprint_issues['all'])
            
            # Extraire les membres d'équipe et mettre à jour les plages de dates
            for ticket in sprint_issues['all']:
                # Membres d'équipe
                assignee = ticket.get('fields', {}).get('assignee')
                reporter = ticket.get('fields', {}).get('reporter')
                
                if assignee:
                    sprint_data['sprints'][sprint_id]['team_members'].add(assignee)
                    if assignee not in sprint_data['team_members']:
                        sprint_data['team_members'][assignee] = {
                            'tickets_assigned': [],
                            'tickets_reported': []
                        }
                    sprint_data['team_members'][assignee]['tickets_assigned'].append(ticket)
                
                if reporter:
                    sprint_data['sprints'][sprint_id]['team_members'].add(reporter)
                    if reporter not in sprint_data['team_members']:
                        sprint_data['team_members'][reporter] = {
                            'tickets_assigned': [],
                            'tickets_reported': []
                        }
                    sprint_data['team_members'][reporter]['tickets_reported'].append(ticket)
                
                # Plage de dates
                created = ticket.get('fields', {}).get('created')
                if created:
                    created_date = pd.to_datetime(created)
                    if not sprint_data['date_range']['min'] or created_date < sprint_data['date_range']['min']:
                        sprint_data['date_range']['min'] = created_date
                    if not sprint_data['date_range']['max'] or created_date > sprint_data['date_range']['max']:
                        sprint_data['date_range']['max'] = created_date
        
        # Convertir les sets en listes
        for sprint_id in sprint_data['sprints']:
            sprint_data['sprints'][sprint_id]['team_members'] = list(
                sprint_data['sprints'][sprint_id]['team_members']
            )
        
        # Calculer les métriques
        sprint_data = calculate_sprint_metrics(sprint_data)
        
        # Nettoyer l'affichage
        progress_bar.empty()
        status_text.empty()
        
        # Sauvegarder dans le state
        StateManager.set('team_sprint_data', sprint_data)
        StateManager.set('team_sprint_last_update', datetime.now())
        
        st.success(f"✅ Analyse terminée: {len(sprint_data['sprints'])} sprints, "
                  f"{len(sprint_data['team_members'])} membres d'équipe, "
                  f"{len(sprint_data['tickets'])} tickets analysés")
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des sprints: {e}")
        st.error(f"Erreur: {str(e)}")5. Update the calculate_sprint_metrics function to handle the new structure:def calculate_sprint_metrics(sprint_data: Dict[str, Any]) -> Dict[str, Any]:
    """Calcule les métriques pour chaque sprint."""
    for sprint_id, sprint in sprint_data['sprints'].items():
        tickets = sprint['tickets']
        completed_tickets = sprint['completed_tickets']
        incomplete_tickets = sprint['incomplete_tickets']
        moved_out_tickets = sprint['moved_out_tickets']
        
        # Métriques de base
        total_tickets = len(tickets)
        completed_count = len(completed_tickets)
        
        sprint['metrics'] = {
            'total_tickets': total_tickets,
            'completed_tickets': completed_count,
            'completion_rate': (completed_count / total_tickets * 100) if total_tickets > 0 else 0,
            'in_progress': len([t for t in tickets if t.get('fields', {}).get('status', '').lower() == 'in progress']),
            'todo': len([t for t in tickets if t.get('fields', {}).get('status', '').lower() == 'to do']),
            'velocity': completed_count,
            'moved_out_count': len(moved_out_tickets),
            'bug_count': len([t for t in tickets if 'bug' in t.get('fields', {}).get('summary', '').lower()]),
            'critical_count': len([t for t in tickets if t.get('fields', {}).get('priority') == 'Critical']),
            'team_size': len(sprint['team_members']),
            'commitment_accuracy': ((total_tickets - len(moved_out_tickets)) / total_tickets * 100) 
                                  if total_tickets > 0 else 100
        }
        
        # Calculer le temps de cycle moyen
        cycle_times = []
        for ticket in completed_tickets:
            if ticket.get('fields', {}).get('resolutiondate'):
                created = pd.to_datetime(ticket.get('fields', {}).get('created'))
                resolved = pd.to_datetime(ticket.get('fields', {}).get('resolutiondate'))
                cycle_time = (resolved - created).days
                if cycle_time >= 0:
                    cycle_times.append(cycle_time)
        
        sprint['metrics']['avg_cycle_time'] = sum(cycle_times) / len(cycle_times) if cycle_times else 0
        
    # Le reste de la fonction reste identique...
    # (calcul des métriques par membre d'équipe)These updates will:
