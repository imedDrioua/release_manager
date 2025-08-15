def render_sprint_performance(tickets: List[Dict[str, Any]]):
    """Analyse la performance de livraison par sprint."""
    st.subheader("🏃 Analyse de performance par Sprint")
    
    # Extraire les données de sprint
    sprint_data = extract_sprint_data(tickets)
    
    if not sprint_data:
        st.info("Aucune donnée de sprint disponible. Assurez-vous que les tickets ont des informations de sprint.")
        return
    
    # Métriques principales
    display_sprint_metrics(sprint_data)
    
    # Graphiques d'analyse
    col1, col2 = st.columns(2)
    
    with col1:
        # Taux de complétion par sprint
        fig_completion = create_sprint_completion_chart(sprint_data)
        st.plotly_chart(fig_completion, use_container_width=True)
    
    with col2:
        # Distribution des reports
        fig_postponed = create_postponement_distribution(sprint_data)
        st.plotly_chart(fig_postponed, use_container_width=True)
    
    # Analyse détaillée des reports
    fig_movement = create_sprint_movement_analysis(sprint_data)
    st.plotly_chart(fig_movement, use_container_width=True)
    
    # Tableau des tickets les plus reportés
    st.subheader("🔄 Tickets les plus reportés")
    display_most_postponed_tickets(sprint_data)
    
    # Analyse par type de ticket
    fig_type_analysis = create_ticket_type_sprint_analysis(sprint_data)
    st.plotly_chart(fig_type_analysis, use_container_width=True)

def extract_sprint_data(tickets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Extrait et structure les données de sprint des tickets."""
    sprint_data = []
    
    for ticket in tickets:
        # Récupérer l'historique des sprints depuis le changelog
        sprint_history = []
        initial_sprint = None
        final_sprint = None
        
        # Vérifier le champ sprint actuel
        current_sprints = ticket.get('fields', {}).get('sprint', [])
        if isinstance(current_sprints, list) and current_sprints:
            # JIRA retourne souvent une liste de sprints
            final_sprint = current_sprints[-1] if isinstance(current_sprints[-1], dict) else {'name': str(current_sprints[-1])}
        
        # Analyser le changelog pour l'historique des sprints
        if 'changelog' in ticket:
            for change in ticket['changelog']:
                if change.get('field', '').lower() == 'sprint':
                    sprint_from = change.get('from', '')
                    sprint_to = change.get('to', '')
                    
                    if not initial_sprint and sprint_from:
                        initial_sprint = {'name': sprint_from}
                    
                    sprint_history.append({
                        'from': sprint_from,
                        'to': sprint_to,
                        'date': change.get('created')
                    })
        
        # Si pas d'historique mais un sprint actuel, c'est le sprint initial
        if not initial_sprint and final_sprint:
            initial_sprint = final_sprint
        
        if initial_sprint or final_sprint:
            sprint_count = len(sprint_history) + 1 if sprint_history else 1
            is_completed = ticket.get('fields', {}).get('status', '').lower() in [
                'done', 'delivery done', 'pushed to master git', 'no git involved'
            ]
            
            sprint_data.append({
                'ticket': ticket['key'],
                'summary': ticket.get('fields', {}).get('summary', ''),
                'status': ticket.get('fields', {}).get('status', ''),
                'priority': ticket.get('fields', {}).get('priority', ''),
                'components': ticket.get('fields', {}).get('components', []),
                'initial_sprint': initial_sprint.get('name') if initial_sprint else None,
                'final_sprint': final_sprint.get('name') if final_sprint else None,
                'sprint_history': sprint_history,
                'sprint_count': sprint_count,
                'is_completed': is_completed,
                'completed_in_first_sprint': is_completed and sprint_count == 1,
                'times_postponed': sprint_count - 1,
                'created_date': ticket.get('fields', {}).get('created'),
                'resolved_date': ticket.get('fields', {}).get('resolutiondate')
            })
    
    return sprint_data

def display_sprint_metrics(sprint_data: List[Dict[str, Any]]):
    """Affiche les métriques principales de performance sprint."""
    total_tickets = len(sprint_data)
    completed_tickets = len([t for t in sprint_data if t['is_completed']])
    completed_first_sprint = len([t for t in sprint_data if t['completed_in_first_sprint']])
    
    # Tickets reportés au moins une fois
    postponed_tickets = len([t for t in sprint_data if t['times_postponed'] > 0])
    
    # Moyenne de reports
    avg_postponements = sum(t['times_postponed'] for t in sprint_data) / total_tickets if total_tickets > 0 else 0
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric("Total avec sprint", total_tickets)
    
    with col2:
        first_sprint_rate = (completed_first_sprint / completed_tickets * 100) if completed_tickets > 0 else 0
        st.metric("Livrés 1er sprint", f"{completed_first_sprint}", f"{first_sprint_rate:.1f}%")
    
    with col3:
        postponed_rate = (postponed_tickets / total_tickets * 100) if total_tickets > 0 else 0
        st.metric("Tickets reportés", postponed_tickets, f"{postponed_rate:.1f}%")
    
    with col4:
        st.metric("Moy. reports/ticket", f"{avg_postponements:.2f}")
    
    with col5:
        max_postponements = max((t['times_postponed'] for t in sprint_data), default=0)
        st.metric("Max reports", max_postponements)

def create_sprint_completion_chart(sprint_data: List[Dict[str, Any]]) -> go.Figure:
    """Crée un graphique du taux de complétion par nombre de sprints."""
    # Grouper par nombre de sprints nécessaires
    completion_by_sprints = {}
    
    for ticket in sprint_data:
        if ticket['is_completed']:
            sprint_count = ticket['sprint_count']
            if sprint_count not in completion_by_sprints:
                completion_by_sprints[sprint_count] = 0
            completion_by_sprints[sprint_count] += 1
    
    # Trier et préparer les données
    sorted_data = sorted(completion_by_sprints.items())
    sprints = [str(s[0]) for s in sorted_data]
    counts = [s[1] for s in sorted_data]
    
    # Calculer les pourcentages cumulés
    total = sum(counts)
    cumulative = []
    cum_sum = 0
    for count in counts:
        cum_sum += count
        cumulative.append(cum_sum / total * 100)
    
    fig = go.Figure()
    
    # Barres pour le nombre de tickets
    fig.add_trace(go.Bar(
        x=sprints,
        y=counts,
        name='Nombre de tickets',
        marker_color='#3498db',
        yaxis='y',
        text=counts,
        textposition='auto'
    ))
    
    # Ligne pour le pourcentage cumulé
    fig.add_trace(go.Scatter(
        x=sprints,
        y=cumulative,
        name='% Cumulé',
        mode='lines+markers+text',
        line=dict(color='#e74c3c', width=3),
        yaxis='y2',
        text=[f"{c:.1f}%" for c in cumulative],
        textposition='top center'
    ))
    
    fig.update_layout(
        title="Nombre de sprints nécessaires pour livrer",
        xaxis_title="Nombre de sprints",
        yaxis=dict(title="Nombre de tickets", side='left'),
        yaxis2=dict(title="Pourcentage cumulé", side='right', overlaying='y', range=[0, 105]),
        height=400,
        hovermode='x unified'
    )
    
    return fig

def create_postponement_distribution(sprint_data: List[Dict[str, Any]]) -> go.Figure:
    """Crée un graphique de distribution des reports."""
    postponement_counts = {}
    
    for ticket in sprint_data:
        postponements = ticket['times_postponed']
        if postponements not in postponement_counts:
            postponement_counts[postponements] = 0
        postponement_counts[postponements] += 1
    
    # Créer des labels descriptifs
    labels = []
    values = []
    colors = []
    
    for postponements, count in sorted(postponement_counts.items()):
        if postponements == 0:
            labels.append("Jamais reporté")
            colors.append('#2ecc71')
        elif postponements == 1:
            labels.append("Reporté 1 fois")
            colors.append('#f39c12')
        elif postponements == 2:
            labels.append("Reporté 2 fois")
            colors.append('#e67e22')
        else:
            labels.append(f"Reporté {postponements}+ fois")
            colors.append('#e74c3c')
        values.append(count)
    
    fig = go.Figure(data=[
        go.Pie(
            labels=labels,
            values=values,
            hole=0.3,
            marker=dict(colors=colors),
            textinfo='label+percent',
            textposition='auto'
        )
    ])
    
    fig.update_layout(
        title="Distribution des reports de sprint",
        height=400
    )
    
    return fig

def create_sprint_movement_analysis(sprint_data: List[Dict[str, Any]]) -> go.Figure:
    """Analyse les mouvements entre sprints."""
    # Analyser les patterns de report par priorité
    priority_analysis = {
        'Critical': {'completed_first': 0, 'postponed': 0},
        'High': {'completed_first': 0, 'postponed': 0},
        'Medium': {'completed_first': 0, 'postponed': 0},
        'Low': {'completed_first': 0, 'postponed': 0}
    }
    
    for ticket in sprint_data:
        priority = ticket.get('priority', 'Medium')
        if priority in priority_analysis:
            if ticket['completed_in_first_sprint']:
                priority_analysis[priority]['completed_first'] += 1
            elif ticket['times_postponed'] > 0:
                priority_analysis[priority]['postponed'] += 1
    
    priorities = list(priority_analysis.keys())
    completed_first = [priority_analysis[p]['completed_first'] for p in priorities]
    postponed = [priority_analysis[p]['postponed'] for p in priorities]
    
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        name='Livrés 1er sprint',
        x=priorities,
        y=completed_first,
        marker_color='#2ecc71'
    ))
    
    fig.add_trace(go.Bar(
        name='Reportés',
        x=priorities,
        y=postponed,
        marker_color='#e74c3c'
    ))
    
    fig.update_layout(
        title="Performance sprint par priorité",
        xaxis_title="Priorité",
        yaxis_title="Nombre de tickets",
        barmode='group',
        height=400
    )
    
    return fig

def display_most_postponed_tickets(sprint_data: List[Dict[str, Any]]):
    """Affiche les tickets les plus reportés."""
    # Filtrer et trier les tickets reportés
    postponed_tickets = [t for t in sprint_data if t['times_postponed'] > 0]
    postponed_tickets.sort(key=lambda x: x['times_postponed'], reverse=True)
    
    if postponed_tickets[:10]:  # Top 10
        df_postponed = pd.DataFrame([
            {
                'Ticket': t['ticket'],
                'Résumé': t['summary'][:50] + '...' if len(t['summary']) > 50 else t['summary'],
                'Reports': t['times_postponed'],
                'Statut': t['status'],
                'Priorité': t['priority'],
                'Sprint initial': t['initial_sprint'] or 'N/A',
                'Sprint actuel': t['final_sprint'] or 'N/A'
            }
            for t in postponed_tickets[:10]
        ])
        
        st.dataframe(
            df_postponed,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Reports": st.column_config.NumberColumn(
                    "Reports",
                    format="%d 🔄"
                )
            }
        )
    else:
        st.success("Aucun ticket reporté ! Excellente performance sprint.")

def create_ticket_type_sprint_analysis(sprint_data: List[Dict[str, Any]]) -> go.Figure:
    """Analyse la performance sprint par type de ticket (composant)."""
    component_performance = {}
    
    for ticket in sprint_data:
        components = ticket.get('components', [])
        if not components:
            components = ['Sans composant']
        
        for component in components:
            if component not in component_performance:
                component_performance[component] = {
                    'total': 0,
                    'completed_first_sprint': 0,
                    'avg_postponements': []
                }
            
            component_performance[component]['total'] += 1
            if ticket['completed_in_first_sprint']:
                component_performance[component]['completed_first_sprint'] += 1
            component_performance[component]['avg_postponements'].append(ticket['times_postponed'])
    
    # Calculer les taux et moyennes
    components = []
    first_sprint_rates = []
    avg_postponements = []
    
    for comp, data in component_performance.items():
        if data['total'] >= 3:  # Au moins 3 tickets pour être significatif
            components.append(comp)
            rate = (data['completed_first_sprint'] / data['total'] * 100)
            first_sprint_rates.append(rate)
            avg_postponements.append(sum(data['avg_postponements']) / len(data['avg_postponements']))
    
    # Trier par taux de réussite
    sorted_indices = sorted(range(len(first_sprint_rates)), key=lambda i: first_sprint_rates[i], reverse=True)
    components = [components[i] for i in sorted_indices]
    first_sprint_rates = [first_sprint_rates[i] for i in sorted_indices]
    avg_postponements = [avg_postponements[i] for i in sorted_indices]
    
    fig = go.Figure()
    
    # Taux de livraison premier sprint
    fig.add_trace(go.Bar(
        name='Taux livraison 1er sprint (%)',
        x=components,
        y=first_sprint_rates,
        marker_color=['#2ecc71' if r >= 70 else '#f39c12' if r >= 50 else '#e74c3c' for r in first_sprint_rates],
        yaxis='y',
        text=[f"{r:.1f}%" for r in first_sprint_rates],
        textposition='auto'
    ))
    
    # Moyenne de reports
    fig.add_trace(go.Scatter(
        name='Moy. reports',
        x=components,
        y=avg_postponements,
        mode='lines+markers+text',
        line=dict(color='#34495e', width=3),
        yaxis='y2',
        text=[f"{a:.1f}" for a in avg_postponements],
        textposition='top center'
    ))
    
    fig.update_layout(
        title="Performance sprint par composant",
        xaxis_title="Composant",
        yaxis=dict(title="Taux livraison 1er sprint (%)", side='left', range=[0, 105]),
        yaxis2=dict(title="Moyenne reports", side='right', overlaying='y'),
        height=450,
        hovermode='x unified'
    )
    
    return fig