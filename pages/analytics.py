"""Page d'analyse des performances utilisateur."""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import logging
from typing import List, Dict, Any
import numpy as np

from utils.state_manager import StateManager
from utils.charts import ChartGenerator
from api.jira_client import JiraClient
import config

logger = logging.getLogger(__name__)

def render_user_analytics(jira_client: JiraClient):
    """Affiche la page d'analyse utilisateur."""
    st.title("📊 Analyse des performances utilisateur")
    
    # Formulaire de sélection
    with st.form("user_selection_form"):
        col1, col2, col3 = st.columns([2, 1, 1])
        
        with col1:
            username = st.text_input(
                "Nom d'utilisateur",
                placeholder="jean.dupont",
                help="Entrez le nom d'utilisateur JIRA"
            )
        
        with col2:
            role = st.selectbox(
                "Rôle",
                options=["assignee", "reporter"],
                help="Sélectionner le rôle à analyser"
            )
        
        with col3:
            st.write("")  # Espace
            submitted = st.form_submit_button("🔍 Analyser", type="primary")
    
    if submitted and username:
        with st.spinner(f"Récupération des tickets pour {username} en tant que {role}..."):
            tickets = fetch_user_tickets(jira_client, username, role)
            
            if tickets:
                st.success(f"✅ {len(tickets)} tickets trouvés pour {username}")
                
                # Stocker dans le state pour éviter de recharger
                StateManager.set('user_analytics_tickets', tickets)
                StateManager.set('user_analytics_username', username)
                StateManager.set('user_analytics_role', role)
            else:
                st.warning(f"Aucun ticket trouvé pour {username} en tant que {role}")
                return
    
    # Récupérer les données du state
    tickets = StateManager.get('user_analytics_tickets', [])
    username = StateManager.get('user_analytics_username', '')
    role = StateManager.get('user_analytics_role', '')
    
    if not tickets:
        st.info("👆 Entrez un nom d'utilisateur et sélectionnez un rôle pour commencer l'analyse")
        return
    
    # Afficher les analyses
    st.markdown("---")
    st.subheader(f"Analyse pour **{username}** ({role})")
    
    # Métriques principales
    display_main_metrics(tickets, role)
    
    # Onglets pour les différentes visualisations
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📈 Vue d'ensemble", 
        "🗓️ Heatmap Homologation", 
        "⏱️ Temps de cycle",
        "📊 Analyse par composant",
        "🎯 Tendances temporelles"
    ])
    
    with tab1:
        render_overview_tab(tickets, username, role)
    
    with tab2:
        render_homologation_heatmap(tickets)
    
    with tab3:
        render_cycle_time_analysis(tickets)
    
    with tab4:
        render_component_analysis(tickets)
    
    with tab5:
        render_temporal_trends(tickets)

def fetch_user_tickets(jira_client: JiraClient, username: str, role: str) -> List[Dict[str, Any]]:
    """Récupère tous les tickets pour un utilisateur dans un rôle donné."""
    try:
        # Construire la requête JQL
        jql = f'{role} = "{username}" ORDER BY created DESC'
        
        # Récupérer les tickets avec plus de champs pour l'analyse
        fields = config.JIRA_FIELDS + ['resolution', 'resolutiondate', 'timeoriginalestimate', 'timespent']
        
        tickets = jira_client.search_issues(
            jql=jql,
            fields=fields,
            max_results=500  # Augmenter la limite pour avoir un historique complet
        )
        
        logger.info(f"Récupéré {len(tickets)} tickets pour {username} ({role})")
        return tickets
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des tickets: {e}")
        st.error(f"Erreur lors de la récupération des tickets: {str(e)}")
        return []

def display_main_metrics(tickets: List[Dict[str, Any]], role: str):
    """Affiche les métriques principales."""
    # Statuts de livraison
    delivered_statuses = ["delivery done", "pushed to master git", "no git involved"]
    
    # Calculer les métriques
    total_tickets = len(tickets)
    delivered_tickets = len([
        t for t in tickets 
        if t.get('fields', {}).get('status', '').lower() in delivered_statuses
    ])
    delivery_rate = (delivered_tickets / total_tickets * 100) if total_tickets > 0 else 0
    
    # Tickets par priorité
    high_priority = len([t for t in tickets if t.get('fields', {}).get('priority') == 'High'])
    critical_tickets = len([t for t in tickets if t.get('fields', {}).get('priority') == 'Critical'])
    
    # Affichage des métriques
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric("Total tickets", total_tickets)
    
    with col2:
        st.metric(
            "Tickets livrés", 
            delivered_tickets,
            f"{delivery_rate:.1f}%"
        )
    
    with col3:
        st.metric("Taux de livraison", f"{delivery_rate:.1f}%")
    
    with col4:
        st.metric("Haute priorité", high_priority)
    
    with col5:
        st.metric("Critiques", critical_tickets)

def render_overview_tab(tickets: List[Dict[str, Any]], username: str, role: str):
    """Affiche l'onglet vue d'ensemble."""
    col1, col2 = st.columns(2)
    
    with col1:
        # Distribution par statut
        fig_status = create_status_distribution(tickets)
        st.plotly_chart(fig_status, use_container_width=True)
    
    with col2:
        # Distribution par priorité
        fig_priority = create_priority_distribution(tickets)
        st.plotly_chart(fig_priority, use_container_width=True)
    
    # Évolution du nombre de tickets dans le temps
    fig_timeline = create_ticket_timeline(tickets)
    st.plotly_chart(fig_timeline, use_container_width=True)
    
    # Tableau récapitulatif des statuts de livraison
    st.subheader("📋 Détail des tickets livrés")
    delivered_statuses = ["delivery done", "pushed to master git", "no git involved"]
    delivered_tickets = [
        t for t in tickets 
        if t.get('fields', {}).get('status', '').lower() in delivered_statuses
    ]
    
    if delivered_tickets:
        df_delivered = pd.DataFrame([
            {
                'Ticket': t['key'],
                'Résumé': t.get('fields', {}).get('summary', '')[:60] + '...',
                'Statut': t.get('fields', {}).get('status', ''),
                'Priorité': t.get('fields', {}).get('priority', ''),
                'Date de livraison': pd.to_datetime(t.get('fields', {}).get('resolutiondate', '')).strftime('%d/%m/%Y') 
                    if t.get('fields', {}).get('resolutiondate') else 'N/A'
            }
            for t in delivered_tickets
        ])
        st.dataframe(df_delivered, use_container_width=True, hide_index=True)
    else:
        st.info("Aucun ticket livré trouvé")

def render_homologation_heatmap(tickets: List[Dict[str, Any]]):
    """Affiche la heatmap des homologations par jour de la semaine."""
    st.subheader("🗓️ Heatmap des homologations")
    
    # Filtrer les tickets avec statut "homologation done"
    homologation_tickets = []
    for ticket in tickets:
        # Chercher dans l'historique le passage à "homologation done"
        if 'changelog' in ticket:
            for change in ticket['changelog']:
                if (change.get('field', '').lower() == 'status' and 
                    change.get('to', '').lower() == 'homologation done'):
                    homologation_tickets.append({
                        'ticket': ticket['key'],
                        'date': pd.to_datetime(change['created']),
                        'weekday': pd.to_datetime(change['created']).dayofweek,
                        'hour': pd.to_datetime(change['created']).hour
                    })
    
    if not homologation_tickets:
        st.info("Aucun ticket n'a atteint le statut 'homologation done'")
        return
    
    # Créer le DataFrame
    df_homolog = pd.DataFrame(homologation_tickets)
    
    # Heatmap par jour de la semaine
    weekday_counts = df_homolog.groupby('weekday').size().reindex(range(7), fill_value=0)
    days_fr = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']
    
    fig_weekday = go.Figure(data=[
        go.Bar(
            x=days_fr,
            y=weekday_counts.values,
            marker_color=['#3498db' if i < 5 else '#95a5a6' for i in range(7)],
            text=weekday_counts.values,
            textposition='auto'
        )
    ])
    
    fig_weekday.update_layout(
        title="Nombre d'homologations par jour de la semaine",
        xaxis_title="Jour",
        yaxis_title="Nombre d'homologations",
        height=400
    )
    
    st.plotly_chart(fig_weekday, use_container_width=True)
    
    # Heatmap détaillée par jour et heure
    pivot_table = df_homolog.pivot_table(
        values='ticket',
        index='hour',
        columns='weekday',
        aggfunc='count',
        fill_value=0
    )
    
    # S'assurer que toutes les heures et jours sont présents
    full_hours = list(range(24))
    full_days = list(range(7))
    pivot_table = pivot_table.reindex(index=full_hours, columns=full_days, fill_value=0)
    
    fig_heatmap = go.Figure(data=go.Heatmap(
        z=pivot_table.values,
        x=days_fr,
        y=[f"{h:02d}h" for h in full_hours],
        colorscale='Blues',
        hoverongaps=False,
        hovertemplate='%{x}<br>%{y}<br>%{z} homologations<extra></extra>'
    ))
    
    fig_heatmap.update_layout(
        title="Répartition des homologations par jour et heure",
        xaxis_title="Jour de la semaine",
        yaxis_title="Heure de la journée",
        height=600
    )
    
    st.plotly_chart(fig_heatmap, use_container_width=True)
    
    # Statistiques supplémentaires
    col1, col2, col3 = st.columns(3)
    
    with col1:
        most_common_day = days_fr[weekday_counts.idxmax()]
        st.metric("Jour le plus fréquent", most_common_day)
    
    with col2:
        avg_per_week = len(homologation_tickets) / ((df_homolog['date'].max() - df_homolog['date'].min()).days / 7)
        st.metric("Moyenne par semaine", f"{avg_per_week:.1f}")
    
    with col3:
        weekend_ratio = (weekday_counts[5:].sum() / weekday_counts.sum() * 100) if weekday_counts.sum() > 0 else 0
        st.metric("% Weekend", f"{weekend_ratio:.1f}%")

def render_cycle_time_analysis(tickets: List[Dict[str, Any]]):
    """Analyse le temps de cycle des tickets."""
    st.subheader("⏱️ Analyse du temps de cycle")
    
    cycle_times = []
    for ticket in tickets:
        created = ticket.get('fields', {}).get('created')
        resolved = ticket.get('fields', {}).get('resolutiondate')
        
        if created and resolved:
            created_date = pd.to_datetime(created)
            resolved_date = pd.to_datetime(resolved)
            cycle_time = (resolved_date - created_date).days
            
            if cycle_time >= 0:  # Éviter les valeurs négatives
                cycle_times.append({
                    'ticket': ticket['key'],
                    'cycle_time': cycle_time,
                    'priority': ticket.get('fields', {}).get('priority', 'Medium'),
                    'status': ticket.get('fields', {}).get('status', ''),
                    'created': created_date,
                    'resolved': resolved_date
                })
    
    if not cycle_times:
        st.info("Pas assez de données pour l'analyse du temps de cycle")
        return
    
    df_cycle = pd.DataFrame(cycle_times)
    
    # Distribution des temps de cycle
    fig_dist = px.histogram(
        df_cycle,
        x='cycle_time',
        nbins=30,
        title="Distribution des temps de cycle (jours)",
        labels={'cycle_time': 'Temps de cycle (jours)', 'count': 'Nombre de tickets'}
    )
    fig_dist.update_traces(marker_color='#3498db')
    st.plotly_chart(fig_dist, use_container_width=True)
    
    # Temps de cycle par priorité
    fig_priority = px.box(
        df_cycle,
        x='priority',
        y='cycle_time',
        title="Temps de cycle par priorité",
        labels={'cycle_time': 'Temps de cycle (jours)', 'priority': 'Priorité'}
    )
    st.plotly_chart(fig_priority, use_container_width=True)
    
    # Métriques de temps de cycle
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Temps moyen", f"{df_cycle['cycle_time'].mean():.1f} jours")
    
    with col2:
        st.metric("Médiane", f"{df_cycle['cycle_time'].median():.1f} jours")
    
    with col3:
        st.metric("Min", f"{df_cycle['cycle_time'].min()} jours")
    
    with col4:
        st.metric("Max", f"{df_cycle['cycle_time'].max()} jours")
    
    # Top 10 des tickets les plus longs
    st.subheader("🐌 Top 10 des tickets les plus longs")
    top_long = df_cycle.nlargest(10, 'cycle_time')[['ticket', 'cycle_time', 'priority', 'status']]
    st.dataframe(top_long, use_container_width=True, hide_index=True)

def render_component_analysis(tickets: List[Dict[str, Any]]):
    """Analyse par composant."""
    st.subheader("📊 Analyse par composant")
    
    # Préparer les données
    component_data = []
    for ticket in tickets:
        components = ticket.get('fields', {}).get('components', [])
        status = ticket.get('fields', {}).get('status', '')
        priority = ticket.get('fields', {}).get('priority', '')
        
        for component in components:
            component_data.append({
                'component': component,
                'status': status,
                'priority': priority,
                'is_delivered': status.lower() in ["delivery done", "pushed to master git", "no git involved"]
            })
    
    if not component_data:
        st.info("Aucune donnée de composant disponible")
        return
    
    df_comp = pd.DataFrame(component_data)
    
    # Nombre de tickets par composant
    comp_counts = df_comp['component'].value_counts()
    
    fig_comp = go.Figure(data=[
        go.Bar(
            x=comp_counts.index,
            y=comp_counts.values,
            marker_color='#2ecc71',
            text=comp_counts.values,
            textposition='auto'
        )
    ])
    
    fig_comp.update_layout(
        title="Nombre de tickets par composant",
        xaxis_title="Composant",
        yaxis_title="Nombre de tickets",
        height=400
    )
    
    st.plotly_chart(fig_comp, use_container_width=True)
    
    # Taux de livraison par composant
    delivery_by_comp = df_comp.groupby('component').agg({
        'is_delivered': ['sum', 'count']
    })
    delivery_by_comp.columns = ['delivered', 'total']
    delivery_by_comp['rate'] = (delivery_by_comp['delivered'] / delivery_by_comp['total'] * 100).round(1)
    delivery_by_comp = delivery_by_comp.sort_values('rate', ascending=False)
    
    fig_delivery = go.Figure(data=[
        go.Bar(
            x=delivery_by_comp.index,
            y=delivery_by_comp['rate'],
            marker_color=['#2ecc71' if r >= 70 else '#f39c12' if r >= 50 else '#e74c3c' 
                         for r in delivery_by_comp['rate']],
            text=[f"{r}%" for r in delivery_by_comp['rate']],
            textposition='auto'
        )
    ])
    
    fig_delivery.update_layout(
        title="Taux de livraison par composant (%)",
        xaxis_title="Composant",
        yaxis_title="Taux de livraison (%)",
        height=400
    )
    
    st.plotly_chart(fig_delivery, use_container_width=True)

def render_temporal_trends(tickets: List[Dict[str, Any]]):
    """Affiche les tendances temporelles."""
    st.subheader("🎯 Tendances temporelles")
    
    # Préparer les données temporelles
    temporal_data = []
    for ticket in tickets:
        created = ticket.get('fields', {}).get('created')
        if created:
            created_date = pd.to_datetime(created)
            temporal_data.append({
                'date': created_date,
                'month': created_date.to_period('M'),
                'quarter': created_date.to_period('Q'),
                'year': created_date.year,
                'status': ticket.get('fields', {}).get('status', ''),
                'priority': ticket.get('fields', {}).get('priority', ''),
                'is_delivered': ticket.get('fields', {}).get('status', '').lower() in 
                               ["delivery done", "pushed to master git", "no git involved"]
            })
    
    if not temporal_data:
        st.info("Pas de données temporelles disponibles")
        return
    
    df_temporal = pd.DataFrame(temporal_data)
    
    # Évolution mensuelle
    monthly_counts = df_temporal.groupby('month').size()
    monthly_delivered = df_temporal[df_temporal['is_delivered']].groupby('month').size()
    
    fig_monthly = go.Figure()
    
    fig_monthly.add_trace(go.Scatter(
        x=monthly_counts.index.astype(str),
        y=monthly_counts.values,
        mode='lines+markers',
        name='Total créés',
        line=dict(color='#3498db', width=3)
    ))
    
    fig_monthly.add_trace(go.Scatter(
        x=monthly_delivered.index.astype(str),
        y=monthly_delivered.values,
        mode='lines+markers',
        name='Livrés',
        line=dict(color='#2ecc71', width=3)
    ))
    
    fig_monthly.update_layout(
        title="Évolution mensuelle des tickets",
        xaxis_title="Mois",
        yaxis_title="Nombre de tickets",
        height=400,
        hovermode='x unified'
    )
    
    st.plotly_chart(fig_monthly, use_container_width=True)
    
    # Analyse de la vélocité
    st.subheader("🚀 Analyse de la vélocité")
    
    # Calculer la vélocité par période
    recent_months = df_temporal['month'].unique()[-6:]  # 6 derniers mois
    velocity_data = []
    
    for month in recent_months:
        month_data = df_temporal[df_temporal['month'] == month]
        delivered = month_data['is_delivered'].sum()
        total = len(month_data)
        
        velocity_data.append({
            'month': str(month),
            'delivered': delivered,
            'total': total,
            'velocity': delivered / total * 100 if total > 0 else 0
        })
    
    df_velocity = pd.DataFrame(velocity_data)
    
    # Graphique de vélocité
    fig_velocity = go.Figure()
    
    fig_velocity.add_trace(go.Bar(
        x=df_velocity['month'],
        y=df_velocity['velocity'],
        marker_color='#9b59b6',
        text=[f"{v:.1f}%" for v in df_velocity['velocity']],
        textposition='auto',
        name='Vélocité'
    ))
    
    fig_velocity.update_layout(
        title="Vélocité de livraison par mois (%)",
        xaxis_title="Mois",
        yaxis_title="Taux de livraison (%)",
        height=400,
        showlegend=False
    )
    
    st.plotly_chart(fig_velocity, use_container_width=True)
    
    # Métriques de tendance
    col1, col2, col3 = st.columns(3)
    
    with col1:
        avg_velocity = df_velocity['velocity'].mean()
        st.metric("Vélocité moyenne", f"{avg_velocity:.1f}%")
    
    with col2:
        if len(df_velocity) >= 2:
            trend = df_velocity['velocity'].iloc[-1] - df_velocity['velocity'].iloc[-2]
            st.metric("Tendance", f"{'+' if trend > 0 else ''}{trend:.1f}%")
        else:
            st.metric("Tendance", "N/A")
    
    with col3:
        best_month = df_velocity.loc[df_velocity['velocity'].idxmax(), 'month']
        st.metric("Meilleur mois", best_month)

#Fonctions utilitaires pour créer les graphiques
def create_status_distribution(tickets: List[Dict[str, Any]]) -> go.Figure:
    """Crée un graphique de distribution par statut."""
    status_counts = {}
    for ticket in tickets:
        status = ticket.get('fields', {}).get('status', 'Unknown')
        status_counts[status] = status_counts.get(status, 0) + 1
    
    # Trier par nombre décroissant
    sorted_status = sorted(status_counts.items(), key=lambda x: x[1], reverse=True)
    
    fig = go.Figure(data=[
        go.Bar(
            x=[s[0] for s in sorted_status],
            y=[s[1] for s in sorted_status],
            marker_color='#3498db',
            text=[s[1] for s in sorted_status],
            textposition='auto'
        )
    ])
    
    fig.update_layout(
        title="Distribution par statut",
        xaxis_title="Statut",
        yaxis_title="Nombre de tickets",
        height=400
    )
    
    return fig

def create_priority_distribution(tickets: List[Dict[str, Any]]) -> go.Figure:
    """Crée un graphique de distribution par priorité."""
    priority_counts = {}
    priority_colors = {
        'Critical': '#e74c3c',
        'High': '#f39c12',
        'Medium': '#3498db',
        'Low': '#2ecc71'
    }
    
    for ticket in tickets:
        priority = ticket.get('fields', {}).get('priority', 'Medium')
        priority_counts[priority] = priority_counts.get(priority, 0) + 1
    
    fig = go.Figure(data=[
        go.Pie(
            labels=list(priority_counts.keys()),
            values=list(priority_counts.values()),
            hole=0.3,
            marker=dict(
                colors=[priority_colors.get(p, '#95a5a6') for p in priority_counts.keys()]
            )
        )
    ])
    
    fig.update_layout(
        title="Distribution par priorité",
        height=400
    )
    
    return fig

def create_ticket_timeline(tickets: List[Dict[str, Any]]) -> go.Figure:
    """Crée un graphique timeline des tickets."""
    timeline_data = []
    
    for ticket in tickets:
        created = ticket.get('fields', {}).get('created')
        if created:
            timeline_data.append({
                'date': pd.to_datetime(created).date(),
                'type': 'created'
            })
        
        resolved = ticket.get('fields', {}).get('resolutiondate')
        if resolved:
            timeline_data.append({
                'date': pd.to_datetime(resolved).date(),
                'type': 'resolved'
            })
    
    if not timeline_data:
        return ChartGenerator._empty_chart("Pas de données temporelles")
    
    df = pd.DataFrame(timeline_data)
    
    # Agrégation par jour
    created_counts = df[df['type'] == 'created'].groupby('date').size()
    resolved_counts = df[df['type'] == 'resolved'].groupby('date').size()
    
    # Remplir les dates manquantes
    date_range = pd.date_range(start=df['date'].min(), end=df['date'].max(), freq='D')
    created_counts = created_counts.reindex(date_range, fill_value=0)
    resolved_counts = resolved_counts.reindex(date_range, fill_value=0)
    
    # Calcul cumulatif
    created_cumsum = created_counts.cumsum()
    resolved_cumsum = resolved_counts.cumsum()
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=created_cumsum.index,
        y=created_cumsum.values,
        mode='lines',
        name='Tickets créés (cumulatif)',
        line=dict(color='#3498db', width=2)
    ))
    
    fig.add_trace(go.Scatter(
        x=resolved_cumsum.index,
        y=resolved_cumsum.values,
        mode='lines',
        name='Tickets résolus (cumulatif)',
        line=dict(color='#2ecc71', width=2)
    ))
    
    fig.update_layout(
        title="Évolution cumulative des tickets",
        xaxis_title="Date",
        yaxis_title="Nombre de tickets",
        height=400,
        hovermode='x unified'
    )
    
    return fig