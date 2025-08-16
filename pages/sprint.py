"""Page d'analyse des sprints d'équipe."""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import logging
from typing import List, Dict, Any, Tuple
import numpy as np
import json
from io import BytesIO
import base64

from utils.state_manager import StateManager
from api.jira_client import JiraClient
import config

logger = logging.getLogger(__name__)

def render_team_sprint_analysis(jira_client: JiraClient):
    """Affiche la page d'analyse des sprints d'équipe."""
    st.title("🏃‍♂️ Analyse des Sprints d'Équipe")
    
    # Boutons d'action principaux
    col1, col2, col3 = st.columns([1, 1, 2])
    
    with col1:
        if st.button("📊 Analyser", type="primary", use_container_width=True):
            with st.spinner("Récupération des données de sprint..."):
                fetch_and_analyze_sprints(jira_client)
    
    with col2:
        sprint_data = StateManager.get('team_sprint_data', {})
        if st.button("📄 Générer Rapport", type="secondary", use_container_width=True, 
                     disabled=not sprint_data):
            generate_management_report()
    
    # Vérifier si des données sont disponibles
    sprint_data = StateManager.get('team_sprint_data', {})
    if not sprint_data:
        st.info("👆 Cliquez sur 'Analyser' pour commencer l'analyse des sprints")
        return
    
    # Filtres en temps réel
    render_filters(sprint_data)
    
    # Appliquer les filtres
    filtered_data = apply_filters(sprint_data)
    
    # Onglets d'analyse
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 Vue d'ensemble",
        "🔄 Comparaison Sprints", 
        "👥 Performance Équipe",
        "📈 Tendances & Vélocité",
        "🎯 Analyse Détaillée"
    ])
    
    with tab1:
        render_overview(filtered_data)
    
    with tab2:
        render_sprint_comparison(filtered_data)
    
    with tab3:
        render_team_performance(filtered_data)
    
    with tab4:
        render_trends_velocity(filtered_data)
    
    with tab5:
        render_detailed_analysis(filtered_data)

def fetch_and_analyze_sprints(jira_client: JiraClient):
    """Récupère et analyse toutes les données de sprint."""
    try:
        # Récupérer tous les sprints actifs et récents
        jql_base = 'project in (PROJ) AND sprint is not EMPTY ORDER BY created DESC'
        fields = config.JIRA_FIELDS + ['sprint', 'resolution', 'resolutiondate', 
                                      'timeoriginalestimate', 'timespent', 'customfield_10100']
        
        all_tickets = jira_client.search_issues(
            jql=jql_base,
            fields=fields,
            max_results=1000
        )
        
        # Organiser les données par sprint et équipe
        sprint_data = organize_sprint_data(all_tickets)
        
        # Calculer les métriques
        sprint_data = calculate_sprint_metrics(sprint_data)
        
        # Sauvegarder dans le state
        StateManager.set('team_sprint_data', sprint_data)
        StateManager.set('team_sprint_last_update', datetime.now())
        
        st.success(f"✅ Analyse terminée: {len(sprint_data['sprints'])} sprints, {len(sprint_data['team_members'])} membres d'équipe")
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des sprints: {e}")
        st.error(f"Erreur: {str(e)}")

def organize_sprint_data(tickets: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Organise les tickets par sprint et équipe."""
    sprint_data = {
        'sprints': {},
        'team_members': {},
        'tickets': tickets,
        'date_range': {'min': None, 'max': None}
    }
    
    for ticket in tickets:
        # Extraire les sprints
        sprints = ticket.get('fields', {}).get('sprint', [])
        if not isinstance(sprints, list):
            sprints = [sprints] if sprints else []
        
        for sprint in sprints:
            if isinstance(sprint, dict):
                sprint_name = sprint.get('name', 'Unknown Sprint')
                sprint_id = sprint.get('id', sprint_name)
                
                if sprint_id not in sprint_data['sprints']:
                    sprint_data['sprints'][sprint_id] = {
                        'name': sprint_name,
                        'state': sprint.get('state', 'active'),
                        'startDate': sprint.get('startDate'),
                        'endDate': sprint.get('endDate'),
                        'tickets': [],
                        'team_members': set()
                    }
                
                sprint_data['sprints'][sprint_id]['tickets'].append(ticket)
                
                # Ajouter les membres d'équipe
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
        
        # Mettre à jour la plage de dates
        created = ticket.get('fields', {}).get('created')
        if created:
            created_date = pd.to_datetime(created)
            if not sprint_data['date_range']['min'] or created_date < sprint_data['date_range']['min']:
                sprint_data['date_range']['min'] = created_date
            if not sprint_data['date_range']['max'] or created_date > sprint_data['date_range']['max']:
                sprint_data['date_range']['max'] = created_date
    
    # Convertir les sets en listes
    for sprint_id in sprint_data['sprints']:
        sprint_data['sprints'][sprint_id]['team_members'] = list(sprint_data['sprints'][sprint_id]['team_members'])
    
    return sprint_data

def calculate_sprint_metrics(sprint_data: Dict[str, Any]) -> Dict[str, Any]:
    """Calcule les métriques pour chaque sprint."""
    for sprint_id, sprint in sprint_data['sprints'].items():
        tickets = sprint['tickets']
        
        # Métriques de base
        total_tickets = len(tickets)
        completed_tickets = len([t for t in tickets if t.get('fields', {}).get('status', '').lower() in 
                               ['done', 'delivery done', 'pushed to master git', 'no git involved']])
        
        sprint['metrics'] = {
            'total_tickets': total_tickets,
            'completed_tickets': completed_tickets,
            'completion_rate': (completed_tickets / total_tickets * 100) if total_tickets > 0 else 0,
            'in_progress': len([t for t in tickets if t.get('fields', {}).get('status', '').lower() == 'in progress']),
            'todo': len([t for t in tickets if t.get('fields', {}).get('status', '').lower() == 'to do']),
            'velocity': completed_tickets,  # Points de story si disponibles
            'bug_count': len([t for t in tickets if 'bug' in t.get('fields', {}).get('summary', '').lower()]),
            'critical_count': len([t for t in tickets if t.get('fields', {}).get('priority') == 'Critical']),
            'team_size': len(sprint['team_members'])
        }
        
        # Calculer le temps de cycle moyen
        cycle_times = []
        for ticket in tickets:
            if ticket.get('fields', {}).get('resolutiondate'):
                created = pd.to_datetime(ticket.get('fields', {}).get('created'))
                resolved = pd.to_datetime(ticket.get('fields', {}).get('resolutiondate'))
                cycle_time = (resolved - created).days
                if cycle_time >= 0:
                    cycle_times.append(cycle_time)
        
        sprint['metrics']['avg_cycle_time'] = sum(cycle_times) / len(cycle_times) if cycle_times else 0
        
    # Calculer les métriques par membre d'équipe
    for member, data in sprint_data['team_members'].items():
        assigned = data['tickets_assigned']
        reported = data['tickets_reported']
        
        data['metrics'] = {
            'assigned_total': len(assigned),
            'assigned_completed': len([t for t in assigned if t.get('fields', {}).get('status', '').lower() in 
                                     ['done', 'delivery done', 'pushed to master git', 'no git involved']]),
            'reported_total': len(reported),
            'reported_completed': len([t for t in reported if t.get('fields', {}).get('status', '').lower() in 
                                     ['done', 'delivery done', 'pushed to master git', 'no git involved']]),
            'avg_priority': calculate_avg_priority(assigned + reported)
        }
        
        data['metrics']['assigned_completion_rate'] = (
            data['metrics']['assigned_completed'] / data['metrics']['assigned_total'] * 100
            if data['metrics']['assigned_total'] > 0 else 0
        )
        data['metrics']['reported_completion_rate'] = (
            data['metrics']['reported_completed'] / data['metrics']['reported_total'] * 100
            if data['metrics']['reported_total'] > 0 else 0
        )
    
    return sprint_data

def calculate_avg_priority(tickets: List[Dict[str, Any]]) -> float:
    """Calcule la priorité moyenne des tickets."""
    priority_values = {'Critical': 4, 'High': 3, 'Medium': 2, 'Low': 1}
    priorities = [priority_values.get(t.get('fields', {}).get('priority', 'Medium'), 2) for t in tickets]
    return sum(priorities) / len(priorities) if priorities else 2

def render_filters(sprint_data: Dict[str, Any]):
    """Affiche les filtres en temps réel."""
    st.subheader("🔍 Filtres")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        # Filtre par sprint
        sprint_names = [s['name'] for s in sprint_data['sprints'].values()]
        selected_sprints = st.multiselect(
            "Sprints",
            options=sprint_names,
            default=sprint_names[:5] if len(sprint_names) > 5 else sprint_names
        )
        StateManager.set('team_sprint_filter_sprints', selected_sprints)
    
    with col2:
        # Filtre par membre d'équipe
        team_members = list(sprint_data['team_members'].keys())
        selected_members = st.multiselect(
            "Membres d'équipe",
            options=team_members,
            default=[]
        )
        StateManager.set('team_sprint_filter_members', selected_members)
    
    with col3:
        # Filtre par date
        if sprint_data['date_range']['min'] and sprint_data['date_range']['max']:
            date_range = st.date_input(
                "Période",
                value=(sprint_data['date_range']['min'].date(), sprint_data['date_range']['max'].date()),
                min_value=sprint_data['date_range']['min'].date(),
                max_value=sprint_data['date_range']['max'].date(),
                key="team_sprint_date_range"
            )
            StateManager.set('team_sprint_filter_dates', date_range)
    
    with col4:
        # Filtre par statut
        all_statuses = list(set(
            t.get('fields', {}).get('status', '') 
            for t in sprint_data['tickets']
        ))
        selected_statuses = st.multiselect(
            "Statuts",
            options=all_statuses,
            default=[]
        )
        StateManager.set('team_sprint_filter_statuses', selected_statuses)

def apply_filters(sprint_data: Dict[str, Any]) -> Dict[str, Any]:
    """Applique les filtres sélectionnés aux données."""
    filtered_data = {
        'sprints': {},
        'team_members': {},
        'tickets': []
    }
    
    selected_sprints = StateManager.get('team_sprint_filter_sprints', [])
    selected_members = StateManager.get('team_sprint_filter_members', [])
    selected_dates = StateManager.get('team_sprint_filter_dates', None)
    selected_statuses = StateManager.get('team_sprint_filter_statuses', [])
    
    # Filtrer les sprints
    for sprint_id, sprint in sprint_data['sprints'].items():
        if not selected_sprints or sprint['name'] in selected_sprints:
            filtered_tickets = sprint['tickets']
            
            # Filtrer par membre d'équipe
            if selected_members:
                filtered_tickets = [
                    t for t in filtered_tickets
                    if t.get('fields', {}).get('assignee') in selected_members or
                       t.get('fields', {}).get('reporter') in selected_members
                ]
            
            # Filtrer par date
            if selected_dates and len(selected_dates) == 2:
                start_date, end_date = selected_dates
                filtered_tickets = [
                    t for t in filtered_tickets
                    if start_date <= pd.to_datetime(t.get('fields', {}).get('created')).date() <= end_date
                ]
            
            # Filtrer par statut
            if selected_statuses:
                filtered_tickets = [
                    t for t in filtered_tickets
                    if t.get('fields', {}).get('status') in selected_statuses
                ]
            
            if filtered_tickets:
                filtered_sprint = sprint.copy()
                filtered_sprint['tickets'] = filtered_tickets
                filtered_sprint['metrics'] = calculate_sprint_metrics_for_tickets(filtered_tickets)
                filtered_data['sprints'][sprint_id] = filtered_sprint
                filtered_data['tickets'].extend(filtered_tickets)
    
    # Recalculer les données des membres d'équipe
    for ticket in filtered_data['tickets']:
        assignee = ticket.get('fields', {}).get('assignee')
        reporter = ticket.get('fields', {}).get('reporter')
        
        if assignee:
            if assignee not in filtered_data['team_members']:
                filtered_data['team_members'][assignee] = {
                    'tickets_assigned': [],
                    'tickets_reported': []
                }
            filtered_data['team_members'][assignee]['tickets_assigned'].append(ticket)
        
        if reporter:
            if reporter not in filtered_data['team_members']:
                filtered_data['team_members'][reporter] = {
                    'tickets_assigned': [],
                    'tickets_reported': []
                }
            filtered_data['team_members'][reporter]['tickets_reported'].append(ticket)
    
    # Recalculer les métriques des membres
    filtered_data = calculate_sprint_metrics(filtered_data)
    
    return filtered_data

def calculate_sprint_metrics_for_tickets(tickets: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calcule les métriques pour un ensemble de tickets."""
    total = len(tickets)
    completed = len([t for t in tickets if t.get('fields', {}).get('status', '').lower() in 
                    ['done', 'delivery done', 'pushed to master git', 'no git involved']])
    
    return {
        'total_tickets': total,
        'completed_tickets': completed,
        'completion_rate': (completed / total * 100) if total > 0 else 0,
        'in_progress': len([t for t in tickets if t.get('fields', {}).get('status', '').lower() == 'in progress']),
        'todo': len([t for t in tickets if t.get('fields', {}).get('status', '').lower() == 'to do']),
        'velocity': completed
    }

def render_overview(data: Dict[str, Any]):
    """Affiche la vue d'ensemble."""
    st.subheader("📊 Vue d'ensemble des sprints")
    
    # Métriques globales
    total_sprints = len(data['sprints'])
    total_tickets = len(data['tickets'])
    total_members = len(data['team_members'])
    
    if total_tickets == 0:
        st.warning("Aucune donnée à afficher avec les filtres sélectionnés")
        return
    
    completed_tickets = len([t for t in data['tickets'] if t.get('fields', {}).get('status', '').lower() in 
                           ['done', 'delivery done', 'pushed to master git', 'no git involved']])
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric("Sprints analysés", total_sprints)
    
    with col2:
        st.metric("Total tickets", total_tickets)
    
    with col3:
        completion_rate = (completed_tickets / total_tickets * 100) if total_tickets > 0 else 0
        st.metric("Taux global", f"{completion_rate:.1f}%")
    
    with col4:
        st.metric("Membres actifs", total_members)
    
    with col5:
        avg_velocity = completed_tickets / total_sprints if total_sprints > 0 else 0
        st.metric("Vélocité moy.", f"{avg_velocity:.1f}")
    
    # Graphique de répartition par statut
    col1, col2 = st.columns(2)
    
    with col1:
        fig_status = create_status_overview_chart(data['tickets'])
        st.plotly_chart(fig_status, use_container_width=True)
    
    with col2:
        fig_priority = create_priority_overview_chart(data['tickets'])
        st.plotly_chart(fig_priority, use_container_width=True)
    
    # Tableau récapitulatif des sprints
    st.subheader("📋 Résumé des sprints")
    df_sprints = create_sprint_summary_dataframe(data['sprints'])
    st.dataframe(
        df_sprints,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Taux (%)": st.column_config.ProgressColumn(
                "Taux (%)",
                min_value=0,
                max_value=100,
            ),
            "Vélocité": st.column_config.NumberColumn(
                "Vélocité",
                format="%d 🎯"
            )
        }
    )
def render_sprint_comparison(data: Dict[str, Any]):
    """Affiche la comparaison entre sprints."""
    st.subheader("🔄 Comparaison des sprints")
    
    if len(data['sprints']) < 2:
        st.info("Au moins 2 sprints nécessaires pour la comparaison")
        return
    
    # Préparer les données pour la comparaison
    sprint_comparison_data = []
    for sprint_id, sprint in data['sprints'].items():
        sprint_comparison_data.append({
            'Sprint': sprint['name'],
            'Total': sprint['metrics']['total_tickets'],
            'Complétés': sprint['metrics']['completed_tickets'],
            'Taux (%)': sprint['metrics']['completion_rate'],
            'Vélocité': sprint['metrics']['velocity'],
            'Cycle moyen': sprint['metrics'].get('avg_cycle_time', 0),
            'Équipe': sprint['metrics']['team_size']
        })
    
    df_comparison = pd.DataFrame(sprint_comparison_data)
    
    # Graphique de comparaison multi-métriques
    fig_comparison = create_sprint_comparison_chart(df_comparison)
    st.plotly_chart(fig_comparison, use_container_width=True)
    
    # Évolution de la vélocité
    fig_velocity = create_velocity_trend_chart(data['sprints'])
    st.plotly_chart(fig_velocity, use_container_width=True)
    
    # Heatmap de performance
    fig_heatmap = create_sprint_performance_heatmap(data['sprints'])
    st.plotly_chart(fig_heatmap, use_container_width=True)

def render_team_performance(data: Dict[str, Any]):
    """Affiche la performance de l'équipe."""
    st.subheader("👥 Performance de l'équipe")
    
    if not data['team_members']:
        st.info("Aucune donnée d'équipe disponible")
        return
    
    # Tableau de performance par membre
    team_performance = []
    for member, member_data in data['team_members'].items():
        metrics = member_data.get('metrics', {})
        team_performance.append({
            'Membre': member,
            'Assigné Total': metrics.get('assigned_total', 0),
            'Assigné Complété': metrics.get('assigned_completed', 0),
            'Taux Assigné (%)': metrics.get('assigned_completion_rate', 0),
            'Reporter Total': metrics.get('reported_total', 0),
            'Reporter Complété': metrics.get('reported_completed', 0),
            'Taux Reporter (%)': metrics.get('reported_completion_rate', 0),
            'Priorité Moy.': metrics.get('avg_priority', 2)
        })
    
    df_team = pd.DataFrame(team_performance)
    df_team = df_team.sort_values('Assigné Total', ascending=False)
    
    # Graphiques de comparaison
    col1, col2 = st.columns(2)
    
    with col1:
        fig_workload = create_team_workload_chart(df_team)
        st.plotly_chart(fig_workload, use_container_width=True)
    
    with col2:
        fig_completion = create_team_completion_chart(df_team)
        st.plotly_chart(fig_completion, use_container_width=True)
    
    # Tableau détaillé
    st.subheader("📊 Détails par membre")
    st.dataframe(
        df_team,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Taux Assigné (%)": st.column_config.ProgressColumn(
                "Taux Assigné (%)",
                min_value=0,
                max_value=100,
            ),
            "Taux Reporter (%)": st.column_config.ProgressColumn(
                "Taux Reporter (%)",
                min_value=0,
                max_value=100,
            ),
            "Priorité Moy.": st.column_config.NumberColumn(
                "Priorité Moy.",
                format="%.1f ⭐"
            )
        }
    )
    
    # Matrice de collaboration
    fig_collab = create_collaboration_matrix(data['tickets'])
    st.plotly_chart(fig_collab, use_container_width=True)

def render_trends_velocity(data: Dict[str, Any]):
    """Affiche les tendances et la vélocité."""
    st.subheader("📈 Tendances & Vélocité")
    
    # Préparer les données temporelles
    temporal_data = prepare_temporal_data(data['sprints'])
    
    if not temporal_data:
        st.info("Pas assez de données pour l'analyse temporelle")
        return
    
    # Graphique de vélocité cumulée
    fig_cumulative = create_cumulative_velocity_chart(temporal_data)
    st.plotly_chart(fig_cumulative, use_container_width=True)
    
    # Burndown/Burnup chart
    col1, col2 = st.columns(2)
    
    with col1:
        fig_burndown = create_burndown_chart(temporal_data)
        st.plotly_chart(fig_burndown, use_container_width=True)
    
    with col2:
        fig_cycle = create_cycle_time_trend(data['tickets'])
        st.plotly_chart(fig_cycle, use_container_width=True)
    
    # Prédictions et projections
    st.subheader("🔮 Projections")
    render_velocity_predictions(temporal_data)

def render_detailed_analysis(data: Dict[str, Any]):
    """Affiche l'analyse détaillée."""
    st.subheader("🎯 Analyse détaillée")
    
    # Sélecteur de sprint pour analyse approfondie
    sprint_names = [s['name'] for s in data['sprints'].values()]
    if not sprint_names:
        st.info("Aucun sprint disponible pour l'analyse détaillée")
        return
    
    selected_sprint_name = st.selectbox("Sélectionner un sprint", sprint_names)
    
    # Trouver le sprint sélectionné
    selected_sprint = None
    for sprint in data['sprints'].values():
        if sprint['name'] == selected_sprint_name:
            selected_sprint = sprint
            break
    
    if not selected_sprint:
        return
    
    # Métriques détaillées du sprint
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Tickets total", selected_sprint['metrics']['total_tickets'])
    
    with col2:
        st.metric("Complétés", selected_sprint['metrics']['completed_tickets'])
    
    with col3:
        st.metric("En cours", selected_sprint['metrics']['in_progress'])
    
    with col4:
        st.metric("À faire", selected_sprint['metrics']['todo'])
    
    # Analyse par composant
    fig_component = create_sprint_component_analysis(selected_sprint['tickets'])
    st.plotly_chart(fig_component, use_container_width=True)
    
    # Analyse des blocages
    st.subheader("🚧 Analyse des blocages")
    blocked_tickets = identify_blocked_tickets(selected_sprint['tickets'])
    if blocked_tickets:
        df_blocked = pd.DataFrame(blocked_tickets)
        st.dataframe(df_blocked, use_container_width=True, hide_index=True)
    else:
        st.success("Aucun ticket bloqué identifié")
    
    # Recommandations
    st.subheader("💡 Recommandations")
    recommendations = generate_sprint_recommendations(selected_sprint)
    for rec in recommendations:
        st.info(rec)

def generate_management_report():
    """Génère un rapport structuré pour le management."""
    sprint_data = StateManager.get('team_sprint_data', {})
    filtered_data = apply_filters(sprint_data)
    
    # Créer le contenu du rapport
    report_content = f"""
# Rapport d'Analyse des Sprints d'Équipe
**Date de génération:** {datetime.now().strftime('%d/%m/%Y %H:%M')}

## Résumé Exécutif

- **Période analysée:** {len(filtered_data['sprints'])} sprints
- **Équipe:** {len(filtered_data['team_members'])} membres
- **Total tickets:** {len(filtered_data['tickets'])}
- **Taux de complétion global:** {calculate_global_completion_rate(filtered_data):.1f}%
- **Vélocité moyenne:** {calculate_average_velocity(filtered_data):.1f} tickets/sprint

## Métriques Clés

### Performance par Sprint
{generate_sprint_metrics_table(filtered_data['sprints'])}

### Performance de l'Équipe
{generate_team_performance_table(filtered_data['team_members'])}

## Analyse des Tendances

### Évolution de la Vélocité
La vélocité de l'équipe montre une tendance {analyze_velocity_trend(filtered_data)}.

### Points d'Attention
{generate_attention_points(filtered_data)}

## Recommandations

{generate_recommendations(filtered_data)}

## Annexes

### Détail des Métriques
- Taux de bugs: {calculate_bug_rate(filtered_data):.1f}%
- Temps de cycle moyen: {calculate_average_cycle_time(filtered_data):.1f} jours
- Tickets critiques: {count_critical_tickets(filtered_data)}

---
*Rapport généré automatiquement par Release Manager*
"""
    
    # Sauvegarder le rapport
    st.download_button(
        label="📥 Télécharger le rapport (Markdown)",
        data=report_content,
        file_name=f"rapport_sprints_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
        mime="text/markdown"
    )
    
    # Générer aussi une version HTML avec graphiques
    html_report = generate_html_report_with_charts(filtered_data, report_content)
    st.download_button(
        label="📥 Télécharger le rapport complet (HTML)",
        data=html_report,
        file_name=f"rapport_sprints_complet_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html",
        mime="text/html"
    )
    
    st.success("✅ Rapport généré avec succès!")

# Fonctions utilitaires pour les graphiques et analyses

def create_status_overview_chart(tickets: List[Dict[str, Any]]) -> go.Figure:
    """Crée un graphique de répartition par statut."""
    status_counts = {}
    for ticket in tickets:
        status = ticket.get('fields', {}).get('status', 'Unknown')
        status_counts[status] = status_counts.get(status, 0) + 1
    
    fig = go.Figure(data=[go.Pie(
        labels=list(status_counts.keys()),
        values=list(status_counts.values()),
        hole=0.3
    )])
    
    fig.update_layout(
        title="Répartition par statut",
        height=400
    )
    return fig

def create_priority_overview_chart(tickets: List[Dict[str, Any]]) -> go.Figure:
    """Crée un graphique de répartition par priorité."""
    priority_counts = {}
    for ticket in tickets:
        priority = ticket.get('fields', {}).get('priority', 'Medium')
        priority_counts[priority] = priority_counts.get(priority, 0) + 1
    
    colors = {'Critical': '#e74c3c', 'High': '#f39c12', 'Medium': '#3498db', 'Low': '#2ecc71'}
    
    fig = go.Figure(data=[go.Bar(
        x=list(priority_counts.keys()),
        y=list(priority_counts.values()),
        marker_color=[colors.get(p, '#95a5a6') for p in priority_counts.keys()]
    )])
    
    fig.update_layout(
        title="Distribution par priorité",
        xaxis_title="Priorité",
        yaxis_title="Nombre de tickets",
        height=400
    )
    return fig

def create_sprint_summary_dataframe(sprints: Dict[str, Any]) -> pd.DataFrame:
    """Crée un DataFrame résumé des sprints."""
    summary_data = []
    for sprint_id, sprint in sprints.items():
        summary_data.append({
            'Sprint': sprint['name'],
            'État': sprint.get('state', 'active'),
            'Total': sprint['metrics']['total_tickets'],
            'Complétés': sprint['metrics']['completed_tickets'],
            'Taux (%)': sprint['metrics']['completion_rate'],
            'Vélocité': sprint['metrics']['velocity'],
            'Équipe': sprint['metrics']['team_size']
        })
    
    return pd.DataFrame(summary_data)

def create_sprint_comparison_chart(df: pd.DataFrame) -> go.Figure:
    """Crée un graphique de comparaison multi-métriques des sprints."""
    fig = go.Figure()
    
    # Normaliser les valeurs pour la comparaison
    metrics = ['Total', 'Complétés', 'Taux (%)', 'Vélocité']
    
    for metric in metrics:
        fig.add_trace(go.Scatter(
            x=df['Sprint'],
            y=df[metric],
            mode='lines+markers',
            name=metric,
            yaxis='y' if metric != 'Taux (%)' else 'y2'
        ))
    
    fig.update_layout(
        title="Comparaison multi-métriques des sprints",
        xaxis_title="Sprint",
        yaxis=dict(title="Valeurs", side="left"),
        yaxis2=dict(title="Taux (%)", side="right", overlaying="y", range=[0, 100]),
        height=500,
        hovermode='x unified'
    )
    
    return fig

def create_velocity_trend_chart(sprints: Dict[str, Any]) -> go.Figure:
    """Crée un graphique de tendance de vélocité."""
    sprint_names = []
    velocities = []
    completion_rates = []
    
    for sprint in sprints.values():
        sprint_names.append(sprint['name'])
        velocities.append(sprint['metrics']['velocity'])
        completion_rates.append(sprint['metrics']['completion_rate'])
    
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        x=sprint_names,
        y=velocities,
        name='Vélocité',
        marker_color='#3498db',
        yaxis='y'
    ))
    
    fig.add_trace(go.Scatter(
        x=sprint_names,
        y=completion_rates,
        name='Taux de complétion (%)',
        mode='lines+markers',
        line=dict(color='#e74c3c', width=3),
        yaxis='y2'
    ))
    
    # Ajouter une ligne de tendance
    if len(velocities) > 1:
        z = np.polyfit(range(len(velocities)), velocities, 1)
        p = np.poly1d(z)
        fig.add_trace(go.Scatter(
            x=sprint_names,
            y=p(range(len(velocities))),
            name='Tendance vélocité',
            mode='lines',
            line=dict(color='#2ecc71', dash='dash'),
            yaxis='y'
        ))
    
    fig.update_layout(
        title="Évolution de la vélocité et du taux de complétion",
        xaxis_title="Sprint",
        yaxis=dict(title="Vélocité", side="left"),
        yaxis2=dict(title="Taux (%)", side="right", overlaying="y", range=[0, 105]),
        height=450,
        hovermode='x unified'
    )
    
    return fig
def create_sprint_performance_heatmap(sprints: Dict[str, Any]) -> go.Figure:
    """Crée une heatmap de performance des sprints."""
    metrics = ['completion_rate', 'velocity', 'avg_cycle_time', 'team_size']
    metric_names = ['Taux complétion', 'Vélocité', 'Cycle moyen', 'Taille équipe']
    sprint_names = []
    data = []
    
    for sprint in sprints.values():
        sprint_names.append(sprint['name'])
        row = []
        for metric in metrics:
            value = sprint['metrics'].get(metric, 0)
            # Normaliser les valeurs entre 0 et 1
            if metric == 'completion_rate':
                row.append(value / 100)
            elif metric == 'velocity':
                row.append(value / max(s['metrics']['velocity'] for s in sprints.values()) if sprints else 0)
            elif metric == 'avg_cycle_time':
                max_cycle = max(s['metrics'].get('avg_cycle_time', 1) for s in sprints.values())
                row.append(1 - (value / max_cycle) if max_cycle > 0 else 0)  # Inverser pour que moins = mieux
            else:
                max_team = max(s['metrics']['team_size'] for s in sprints.values())
                row.append(value / max_team if max_team > 0 else 0)
        data.append(row)
    
    fig = go.Figure(data=go.Heatmap(
        z=list(map(list, zip(*data))),  # Transposer
        x=sprint_names,
        y=metric_names,
        colorscale='RdYlGn',
        text=[[f"{v:.1%}" for v in row] for row in zip(*data)],
        texttemplate="%{text}",
        textfont={"size": 12}
    ))
    
    fig.update_layout(
        title="Heatmap de performance des sprints",
        xaxis_title="Sprint",
        yaxis_title="Métrique",
        height=400
    )
    
    return fig

def create_team_workload_chart(df: pd.DataFrame) -> go.Figure:
    """Crée un graphique de charge de travail de l'équipe."""
    df_top = df.head(10)  # Top 10 membres
    
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        name='Assigné',
        x=df_top['Membre'],
        y=df_top['Assigné Total'],
        marker_color='#3498db'
    ))
    
    fig.add_trace(go.Bar(
        name='Reporter',
        x=df_top['Membre'],
        y=df_top['Reporter Total'],
        marker_color='#2ecc71'
    ))
    
    fig.update_layout(
        title="Charge de travail par membre (Top 10)",
        xaxis_title="Membre",
        yaxis_title="Nombre de tickets",
        barmode='group',
        height=400
    )
    
    return fig

def create_team_completion_chart(df: pd.DataFrame) -> go.Figure:
    """Crée un graphique des taux de complétion de l'équipe."""
    df_sorted = df.sort_values('Taux Assigné (%)', ascending=True).tail(15)
    
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        name='Taux Assigné',
        x=df_sorted['Taux Assigné (%)'],
        y=df_sorted['Membre'],
        orientation='h',
        marker_color='#e74c3c',
        text=[f"{x:.1f}%" for x in df_sorted['Taux Assigné (%)']],
        textposition='auto'
    ))
    
    # Ligne de référence à 70%
    fig.add_vline(x=70, line_dash="dash", line_color="green", 
                  annotation_text="Objectif 70%")
    
    fig.update_layout(
        title="Taux de complétion par membre",
        xaxis_title="Taux de complétion (%)",
        yaxis_title="Membre",
        height=500,
        xaxis=dict(range=[0, 105])
    )
    
    return fig

def create_collaboration_matrix(tickets: List[Dict[str, Any]]) -> go.Figure:
    """Crée une matrice de collaboration assigné/reporter."""
    collaboration = {}
    
    for ticket in tickets:
        assignee = ticket.get('fields', {}).get('assignee', 'Unknown')
        reporter = ticket.get('fields', {}).get('reporter', 'Unknown')
        
        if assignee not in collaboration:
            collaboration[assignee] = {}
        if reporter not in collaboration[assignee]:
            collaboration[assignee][reporter] = 0
        collaboration[assignee][reporter] += 1
    
    # Convertir en matrice
    all_members = sorted(set(list(collaboration.keys()) + 
                           [r for a in collaboration.values() for r in a.keys()]))
    
    matrix = []
    for reporter in all_members:
        row = []
        for assignee in all_members:
            value = collaboration.get(assignee, {}).get(reporter, 0)
            row.append(value)
        matrix.append(row)
    
    fig = go.Figure(data=go.Heatmap(
        z=matrix,
        x=all_members,
        y=all_members,
        colorscale='Blues',
        text=matrix,
        texttemplate="%{text}",
        textfont={"size": 10}
    ))
    
    fig.update_layout(
        title="Matrice de collaboration (Reporter → Assigné)",
        xaxis_title="Assigné",
        yaxis_title="Reporter",
        height=600
    )
    
    return fig

def prepare_temporal_data(sprints: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Prépare les données temporelles des sprints."""
    temporal_data = []
    
    for sprint in sprints.values():
        if sprint.get('startDate'):
            temporal_data.append({
                'date': pd.to_datetime(sprint['startDate']),
                'sprint': sprint['name'],
                'velocity': sprint['metrics']['velocity'],
                'completion_rate': sprint['metrics']['completion_rate'],
                'total': sprint['metrics']['total_tickets'],
                'completed': sprint['metrics']['completed_tickets']
            })
    
    return sorted(temporal_data, key=lambda x: x['date'])

def create_cumulative_velocity_chart(temporal_data: List[Dict[str, Any]]) -> go.Figure:
    """Crée un graphique de vélocité cumulée."""
    dates = [d['date'] for d in temporal_data]
    velocities = [d['velocity'] for d in temporal_data]
    cumulative_velocity = np.cumsum(velocities)
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=dates,
        y=velocities,
        mode='lines+markers',
        name='Vélocité par sprint',
        line=dict(color='#3498db', width=2)
    ))
    
    fig.add_trace(go.Scatter(
        x=dates,
        y=cumulative_velocity,
        mode='lines+markers',
        name='Vélocité cumulée',
        line=dict(color='#2ecc71', width=3),
        yaxis='y2'
    ))
    
    fig.update_layout(
        title="Évolution de la vélocité",
        xaxis_title="Date",
        yaxis=dict(title="Vélocité par sprint", side="left"),
        yaxis2=dict(title="Vélocité cumulée", side="right", overlaying="y"),
        height=450,
        hovermode='x unified'
    )
    
    return fig

def create_burndown_chart(temporal_data: List[Dict[str, Any]]) -> go.Figure:
    """Crée un burndown chart."""
    if not temporal_data:
        return go.Figure()
    
    dates = [d['date'] for d in temporal_data]
    remaining = []
    total_initial = sum(d['total'] for d in temporal_data)
    
    cumulative_completed = 0
    for d in temporal_data:
        cumulative_completed += d['completed']
        remaining.append(total_initial - cumulative_completed)
    
    # Ligne idéale
    ideal_burndown = np.linspace(total_initial, 0, len(dates))
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=dates,
        y=remaining,
        mode='lines+markers',
        name='Reste à faire',
        line=dict(color='#e74c3c', width=3)
    ))
    
    fig.add_trace(go.Scatter(
        x=dates,
        y=ideal_burndown,
        mode='lines',
        name='Burndown idéal',
        line=dict(color='#95a5a6', dash='dash')
    ))
    
    fig.update_layout(
        title="Burndown Chart",
        xaxis_title="Date",
        yaxis_title="Tickets restants",
        height=400,
        hovermode='x unified'
    )
    
    return fig

def create_cycle_time_trend(tickets: List[Dict[str, Any]]) -> go.Figure:
    """Crée un graphique de tendance du temps de cycle."""
    cycle_data = []
    
    for ticket in tickets:
        if ticket.get('fields', {}).get('resolutiondate'):
            created = pd.to_datetime(ticket.get('fields', {}).get('created'))
            resolved = pd.to_datetime(ticket.get('fields', {}).get('resolutiondate'))
            cycle_time = (resolved - created).days
            
            if 0 <= cycle_time <= 90:  # Filtrer les valeurs aberrantes
                cycle_data.append({
                    'date': resolved,
                    'cycle_time': cycle_time,
                    'priority': ticket.get('fields', {}).get('priority', 'Medium')
                })
    
    if not cycle_data:
        return go.Figure()
    
    df = pd.DataFrame(cycle_data)
    df = df.sort_values('date')
    
    # Moyenne mobile sur 10 tickets
    df['cycle_ma'] = df['cycle_time'].rolling(window=10, min_periods=1).mean()
    
    fig = go.Figure()
    
    # Points individuels
    for priority in ['Critical', 'High', 'Medium', 'Low']:
        df_priority = df[df['priority'] == priority]
        if not df_priority.empty:
            fig.add_trace(go.Scatter(
                x=df_priority['date'],
                y=df_priority['cycle_time'],
                mode='markers',
                name=f'{priority}',
                opacity=0.6
            ))
    
    # Moyenne mobile
    fig.add_trace(go.Scatter(
        x=df['date'],
        y=df['cycle_ma'],
        mode='lines',
        name='Moyenne mobile',
        line=dict(color='black', width=3)
    ))
    
    fig.update_layout(
        title="Évolution du temps de cycle",
        xaxis_title="Date de résolution",
        yaxis_title="Temps de cycle (jours)",
        height=400,
        hovermode='x unified'
    )
    
    return fig

def render_velocity_predictions(temporal_data: List[Dict[str, Any]]):
    """Affiche les prédictions de vélocité."""
    if len(temporal_data) < 3:
        st.info("Pas assez de données pour les projections")
        return
    
    velocities = [d['velocity'] for d in temporal_data]
    dates = [d['date'] for d in temporal_data]
    
    # Régression linéaire simple
    x = np.arange(len(velocities))
    z = np.polyfit(x, velocities, 1)
    p = np.poly1d(z)
    
    # Projections pour les 3 prochains sprints
    future_x = np.arange(len(velocities), len(velocities) + 3)
    future_velocities = p(future_x)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        trend = "croissante" if z[0] > 0 else "décroissante"
        st.metric("Tendance", trend, f"{z[0]:.2f} tickets/sprint")
    
    with col2:
        next_velocity = max(0, future_velocities[0])
        st.metric("Vélocité projetée prochain sprint", f"{next_velocity:.1f}")
    
    with col3:
        avg_3_sprints = max(0, np.mean(future_velocities))
        st.metric("Moyenne 3 prochains sprints", f"{avg_3_sprints:.1f}")

def create_sprint_component_analysis(tickets: List[Dict[str, Any]]) -> go.Figure:
    """Analyse par composant pour un sprint."""
    component_status = {}
    
    for ticket in tickets:
        components = ticket.get('fields', {}).get('components', ['Sans composant'])
        status = ticket.get('fields', {}).get('status', 'Unknown')
        
        for component in components:
            if component not in component_status:
                component_status[component] = {}
            if status not in component_status[component]:
                component_status[component][status] = 0
            component_status[component][status] += 1
    
    # Préparer les données pour le graphique empilé
    components = list(component_status.keys())
    statuses = list(set(s for c in component_status.values() for s in c.keys()))
    
    fig = go.Figure()
    
    for status in statuses:
        values = [component_status[c].get(status, 0) for c in components]
        fig.add_trace(go.Bar(
            name=status,
            x=components,
            y=values
        ))
    
    fig.update_layout(
        title="Répartition par composant et statut",
        xaxis_title="Composant",
        yaxis_title="Nombre de tickets",
        barmode='stack',
        height=400
    )
    
    return fig

def identify_blocked_tickets(tickets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Identifie les tickets potentiellement bloqués."""
    blocked = []
    
    for ticket in tickets:
        # Critères de blocage
        created = pd.to_datetime(ticket.get('fields', {}).get('created'))
        days_old = (datetime.now() - created).days
        
        if (ticket.get('fields', {}).get('status', '').lower() == 'in progress' and 
            days_old > 14):
            blocked.append({
                'Ticket': ticket['key'],
                'Résumé': ticket.get('fields', {}).get('summary', '')[:50] + '...',
                'Assigné': ticket.get('fields', {}).get('assignee', 'Non assigné'),
                'Jours en cours': days_old,
                'Priorité': ticket.get('fields', {}).get('priority', 'Medium')
            })
    
    return sorted(blocked, key=lambda x: x['Jours en cours'], reverse=True)

def generate_sprint_recommendations(sprint: Dict[str, Any]) -> List[str]:
    """Génère des recommandations pour un sprint."""
    recommendations = []
    metrics = sprint['metrics']
    
    if metrics['completion_rate'] < 70:
        recommendations.append(
            f"⚠️ Taux de complétion faible ({metrics['completion_rate']:.1f}%). "
            "Considérer de réduire le scope des prochains sprints."
        )
    
    if metrics.get('avg_cycle_time', 0) > 10:
        recommendations.append(
            f"⏱️ Temps de cycle élevé ({metrics['avg_cycle_time']:.1f} jours). "
            "Identifier et résoudre les blocages."
        )
    
    if metrics['critical_count'] > metrics['total_tickets'] * 0.3:
        recommendations.append(
            "🔥 Trop de tickets critiques. Revoir la priorisation."
        )
    
    if metrics['team_size'] < 3:
        recommendations.append(
            "👥 Équipe réduite. Risque de surcharge."
        )
    
    if not recommendations:
        recommendations.append("✅ Sprint bien équilibré, continuer ainsi!")
    
    return recommendations

# Fonctions pour la génération du rapport

def calculate_global_completion_rate(data: Dict[str, Any]) -> float:
    """Calcule le taux de complétion global."""
    total = len(data['tickets'])
    completed = len([t for t in data['tickets'] if t.get('fields', {}).get('status', '').lower() in 
                    ['done', 'delivery done', 'pushed to master git', 'no git involved']])
    return (completed / total * 100) if total > 0 else 0

def calculate_average_velocity(data: Dict[str, Any]) -> float:
    """Calcule la vélocité moyenne."""
    if not data['sprints']:
        return 0
    velocities = [s['metrics']['velocity'] for s in data['sprints'].values()]
    return sum(velocities) / len(velocities)

def generate_sprint_metrics_table(sprints: Dict[str, Any]) -> str:
    """Génère un tableau markdown des métriques de sprint."""
    lines = ["| Sprint | Total | Complétés | Taux (%) | Vélocité |",
             "|--------|-------|-----------|----------|----------|"]
    
    for sprint in sprints.values():
        m = sprint['metrics']
        lines.append(f"| {sprint['name']} | {m['total_tickets']} | {m['completed_tickets']} | "
                    f"{m['completion_rate']:.1f} | {m['velocity']} |")
    
    return "\n".join(lines)

def generate_team_performance_table(team_members: Dict[str, Any]) -> str:
    """Génère un tableau de performance d'équipe."""
    lines = ["| Membre | Assigné | Complété | Taux (%) |",
             "|--------|---------|----------|----------|"]
    
    for member, data in sorted(team_members.items(), 
                              key=lambda x: x[1]['metrics']['assigned_total'], 
                              reverse=True)[:10]:
        m = data['metrics']
        lines.append(f"| {member} | {m['assigned_total']} | {m['assigned_completed']} | "
                    f"{m['assigned_completion_rate']:.1f} |")
    
    return "\n".join(lines)

def analyze_velocity_trend(data: Dict[str, Any]) -> str:
    """Analyse la tendance de vélocité."""
    velocities = [s['metrics']['velocity'] for s in data['sprints'].values()]
    if len(velocities) < 2:
        return "insuffisante pour analyse"
    
    # Calculer la tendance
    x = np.arange(len(velocities))
    z = np.polyfit(x, velocities, 1)
    
    if z[0] > 0.5:
        return "croissante ↗️"
    elif z[0] < -0.5:
        return "décroissante ↘️"
    else:
        return "stable →"

def generate_attention_points(data: Dict[str, Any]) -> str:
    """Génère les points d'attention."""
    points = []
    
    # Analyser les métriques
    avg_completion = calculate_global_completion_rate(data)
    if avg_completion < 70:
        points.append(f"- Taux de complétion faible: {avg_completion:.1f}%")
    
    # Tickets bloqués
    blocked_count = 0
    for ticket in data['tickets']:
        if ticket.get('fields', {}).get('status', '').lower() == 'in progress':
            created = pd.to_datetime(ticket.get('fields', {}).get('created'))
            if (datetime.now() - created).days > 14:
                blocked_count += 1
    
    if blocked_count > 0:
        points.append(f"- {blocked_count} tickets potentiellement bloqués")
    
    # Déséquilibre équipe
    workloads = [len(m['tickets_assigned']) for m in data['team_members'].values()]
    if workloads and max(workloads) > 3 * (sum(workloads) / len(workloads)):
        points.append("- Déséquilibre important dans la répartition du travail")
    
    return "\n".join(points) if points else "- Aucun point d'attention majeur"
def generate_recommendations(data: Dict[str, Any]) -> str:
    """Génère des recommandations."""
    recs = []
    
    avg_completion = calculate_global_completion_rate(data)
    if avg_completion < 70:
        recs.append("1. **Réduire le scope des sprints** pour améliorer le taux de complétion")
    
    if len(data['team_members']) < 5:
        recs.append("2. **Renforcer l'équipe** pour augmenter la capacité")
    
    # Analyser la variance des vélocités
    velocities = [s['metrics']['velocity'] for s in data['sprints'].values()]
    if velocities and np.std(velocities) > np.mean(velocities) * 0.3:
        recs.append("3. **Stabiliser la vélocité** en améliorant l'estimation")
    
    if not recs:
        recs.append("L'équipe performe bien. Continuer les bonnes pratiques actuelles.")
    
    return "\n".join(recs)

def calculate_bug_rate(data: Dict[str, Any]) -> float:
    """Calcule le taux de bugs."""
    total = len(data['tickets'])
    bugs = len([t for t in data['tickets'] if 'bug' in t.get('fields', {}).get('summary', '').lower()])
    return (bugs / total * 100) if total > 0 else 0

def calculate_average_cycle_time(data: Dict[str, Any]) -> float:
    """Calcule le temps de cycle moyen."""
    cycle_times = []
    for ticket in data['tickets']:
        if ticket.get('fields', {}).get('resolutiondate'):
            created = pd.to_datetime(ticket.get('fields', {}).get('created'))
            resolved = pd.to_datetime(ticket.get('fields', {}).get('resolutiondate'))
            cycle_time = (resolved - created).days
            if 0 <= cycle_time <= 90:
                cycle_times.append(cycle_time)
    
    return sum(cycle_times) / len(cycle_times) if cycle_times else 0

def count_critical_tickets(data: Dict[str, Any]) -> int:
    """Compte les tickets critiques."""
    return len([t for t in data['tickets'] if t.get('fields', {}).get('priority') == 'Critical'])

def generate_html_report_with_charts(data: Dict[str, Any], markdown_content: str) -> str:
    """Génère un rapport HTML avec graphiques intégrés."""
    import markdown
    
    # Convertir le markdown en HTML
    html_content = markdown.markdown(markdown_content, extensions=['tables'])
    
    # Template HTML complet
    html_template = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Rapport d'Analyse des Sprints</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 1200px;
                margin: 0 auto;
                padding: 20px;
                background-color: #f4f4f4;
            }}
            h1 {{
                color: #2c3e50;
                border-bottom: 3px solid #3498db;
                padding-bottom: 10px;
            }}
            h2 {{
                color: #34495e;
                margin-top: 30px;
            }}
            table {{
                border-collapse: collapse;
                width: 100%;
                margin: 20px 0;
                background-color: white;
                box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            }}
            th, td {{
                border: 1px solid #ddd;
                padding: 12px;
                text-align: left;
            }}
            th {{
                background-color: #3498db;
                color: white;
            }}
            tr:nth-child(even) {{
                background-color: #f9f9f9;
            }}
            .metric {{
                display: inline-block;
                margin: 10px;
                padding: 15px;
                background-color: white;
                border-radius: 5px;
                box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            }}
            .metric-value {{
                font-size: 24px;
                font-weight: bold;
                color: #3498db;
            }}
            .metric-label {{
                font-size: 14px;
                color: #7f8c8d;
            }}
        </style>
    </head>
    <body>
        {html_content}
        <hr>
        <p style="text-align: center; color: #7f8c8d;">
            Généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')}
        </p>
    </body>
    </html>
    """
    
    return html_template