"""
Personal Notes Page for Release Management Application
File: pages/personal_notes.py
"""

import streamlit as st
import pandas as pd
from datetime import datetime

from utils.session_state import get_current_release_id

def show_personal_notes(db_manager):
    """Display the personal notes page"""

    st.title("📝 Personal Notes")

    current_release_id = get_current_release_id()

    # Header controls
    col1, col2 = st.columns([3, 1])

    with col1:
        st.subheader("Manage Your Notes")

    with col2:
        if st.button("➕ New Note", type="primary"):
            st.session_state.notes_state = {"editing_note": "new"}
            st.rerun()

    # Tab layout
    tab1, tab2 = st.tabs(["📋 All Notes", "🎯 Release Notes"])

    with tab1:
        show_all_notes(db_manager, current_release_id)

    with tab2:
        show_release_specific_notes(db_manager, current_release_id)

    # Note editor modal
    show_note_editor(db_manager, current_release_id)

def show_all_notes(db_manager, current_release_id):
    """Display all notes with search and filtering"""

    # Search and filter controls
    col1, col2, col3 = st.columns(3)

    with col1:
        search_query = st.text_input("🔍 Search notes",
                                     value=st.session_state.get('search_query', ''),
                                     key="search_notes")

    with col2:
        note_type_filter = st.selectbox("Filter by type:",
                                        ["All", "Release", "Ticket"])

    with col3:
        sort_by = st.selectbox("Sort by:",
                               ["Last Updated", "Created Date", "Title"])

    # Get notes based on filters
    try:
        if note_type_filter == "All":
            notes = db_manager.get_notes()
        else:
            notes = db_manager.get_notes(note_type=note_type_filter.lower())

        # Apply search filter
        if search_query:
            notes = [note for note in notes
                     if search_query.lower() in note['title'].lower() or
                     search_query.lower() in note['content'].lower()]

        # Sort notes
        if sort_by == "Last Updated":
            notes.sort(key=lambda x: x['updated_at'], reverse=True)
        elif sort_by == "Created Date":
            notes.sort(key=lambda x: x['created_at'], reverse=True)
        else:  # Title
            notes.sort(key=lambda x: x['title'])

        if notes:
            st.write(f"Found {len(notes)} note(s)")

            for note in notes:
                display_note_card(db_manager, note)
        else:
            st.info("No notes found. Create your first note!")

    except Exception as e:
        st.error(f"Error loading notes: {str(e)}")

def show_release_specific_notes(db_manager, current_release_id):
    """Display notes specific to current release"""

    st.subheader(f"Notes for Release: {current_release_id}")

    try:
        release_notes = db_manager.get_notes(note_type="release", release_id=current_release_id)

        if release_notes:
            for note in release_notes:
                display_note_card(db_manager, note)
        else:
            st.info(f"No notes found for release {current_release_id}")

            # Quick create release note
            if st.button("📝 Create First Release Note"):
                st.session_state.notes_state = {
                    "editing_note": "new",
                    "default_type": "release",
                    "default_release_id": current_release_id
                }
                st.rerun()

    except Exception as e:
        st.error(f"Error loading release notes: {str(e)}")

def display_note_card(db_manager, note):
    """Display a single note card"""

    # Determine note color based on type
    color_map = {
        'release': '#e7f3ff',
        'ticket': '#fff3e0'
    }

    bg_color = color_map.get(note['note_type'], '#f8f9fa')

    with st.container():
        st.markdown(f"""
        <div style="
            background-color: {bg_color};
            border: 1px solid #dee2e6;
            border-radius: 8px;
            padding: 1.5rem;
            margin: 1rem 0;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        ">
            <div style="display: flex; justify-content: between; align-items: center; margin-bottom: 1rem;">
                <h4 style="margin: 0; color: #333; flex-grow: 1;">{note['title']}</h4>
                <small style="color: #666; margin-left: 1rem;">
                    {note['note_type'].title()} | {note['updated_at'][:16]}
                </small>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Note content (truncated for display)
        content_preview = note['content'][:200] + "..." if len(note['content']) > 200 else note['content']
        st.markdown(content_preview)

        # Tags if available
        if note.get('tags'):
            tags = [tag.strip() for tag in note['tags'].split(',') if tag.strip()]
            if tags:
                tag_html = " ".join([f'<span style="background-color: #6c757d; color: white; padding: 2px 6px; border-radius: 3px; font-size: 0.8em; margin-right: 5px;">{tag}</span>' for tag in tags])
                st.markdown(f"**Tags:** {tag_html}", unsafe_allow_html=True)

        # Additional info for ticket notes
        if note['note_type'] == 'ticket' and note.get('ticket_key'):
            st.markdown(f"**Related Ticket:** {note['ticket_key']}")

        # Action buttons
        col1, col2, col3, col4 = st.columns([1, 1, 1, 7])

        with col1:
            if st.button("✏️", key=f"edit_{note['id']}", help="Edit note"):
                st.session_state.notes_state = {"editing_note": note['id']}
                st.rerun()

        with col2:
            if st.button("🗑️", key=f"delete_{note['id']}", help="Delete note"):
                if st.session_state.get(f"confirm_delete_{note['id']}"):
                    if db_manager.delete_note(note['id']):
                        st.success("Note deleted!")
                        st.rerun()
                    else:
                        st.error("Failed to delete note")
                else:
                    st.session_state[f"confirm_delete_{note['id']}"] = True
                    st.warning("Click again to confirm deletion")
                    st.rerun()

        with col3:
            # View full note in expander
            with st.expander("👁️", expanded=False):
                st.markdown("**Full Content:**")
                st.markdown(note['content'])

def show_note_editor(db_manager, current_release_id):
    """Show note editor modal"""

    notes_state = st.session_state.get('notes_state', {})
    editing_note = notes_state.get('editing_note')

    if editing_note:
        st.markdown("---")

        if editing_note == "new":
            st.subheader("📝 Create New Note")
            note_data = {
                'title': '',
                'content': '',
                'note_type': notes_state.get('default_type', 'release'),
                'ticket_key': '',
                'release_id': notes_state.get('default_release_id', current_release_id),
                'tags': ''
            }
        else:
            st.subheader("✏️ Edit Note")
            # Get existing note
            try:
                all_notes = db_manager.get_notes()
                note_data = next((note for note in all_notes if note['id'] == editing_note), None)
                if not note_data:
                    st.error("Note not found!")
                    st.session_state.notes_state = {}
                    st.rerun()
                    return
            except Exception as e:
                st.error(f"Error loading note: {str(e)}")
                return

        # Note editor form
        with st.form("note_editor"):
            col1, col2 = st.columns(2)

            with col1:
                title = st.text_input("Note Title", value=note_data.get('title', ''))
                note_type = st.selectbox("Note Type",
                                         options=["release", "ticket"],
                                         index=0 if note_data.get('note_type') == 'release' else 1)

            with col2:
                tags = st.text_input("Tags (comma-separated)",
                                     value=note_data.get('tags', ''))

                if note_type == "ticket":
                    ticket_key = st.text_input("Related Ticket Key",
                                               value=note_data.get('ticket_key', ''))
                else:
                    release_id = st.selectbox("Release",
                                              options=[current_release_id, "week2025.29", "week2025.28"],
                                              index=0)

            content = st.text_area("Note Content",
                                   value=note_data.get('content', ''),
                                   height=200)

            # Form buttons
            col1, col2, col3 = st.columns([1, 1, 8])

            with col1:
                if st.form_submit_button("💾 Save", type="primary"):
                    # Validate inputs
                    if not title.strip():
                        st.error("Please enter a note title")
                    elif not content.strip():
                        st.error("Please enter note content")
                    else:
                        # Save note
                        try:
                            if editing_note == "new":
                                # Create new note
                                success = db_manager.create_note(
                                    title=title.strip(),
                                    content=content.strip(),
                                    note_type=note_type,
                                    ticket_key=ticket_key.strip() if note_type == "ticket" else None,
                                    release_id=release_id if note_type == "release" else None,
                                    tags=tags.strip() if tags.strip() else None
                                )
                                if success:
                                    st.success("Note created successfully!")
                                else:
                                    st.error("Failed to create note")
                            else:
                                # Update existing note
                                success = db_manager.update_note(
                                    note_id=editing_note,
                                    title=title.strip(),
                                    content=content.strip(),
                                    tags=tags.strip() if tags.strip() else None
                                )
                                if success:
                                    st.success("Note updated successfully!")
                                else:
                                    st.error("Failed to update note")

                            if success:
                                st.session_state.notes_state = {}
                                st.rerun()

                        except Exception as e:
                            st.error(f"Error saving note: {str(e)}")

            with col2:
                if st.form_submit_button("❌ Cancel"):
                    st.session_state.notes_state = {}
                    st.rerun()

def create_quick_note_widgets(db_manager, current_release_id):
    """Create quick note widgets for common actions"""

    st.sidebar.markdown("### 🚀 Quick Actions")

    # Quick release note
    if st.sidebar.button("📋 Quick Release Note"):
        st.session_state.notes_state = {
            "editing_note": "new",
            "default_type": "release",
            "default_release_id": current_release_id
        }
        st.rerun()

    # Quick ticket note
    ticket_key = st.sidebar.text_input("Ticket Key for Quick Note",
                                       placeholder="e.g., PROJ-1001")
    if st.sidebar.button("🎫 Quick Ticket Note") and ticket_key:
        st.session_state.notes_state = {
            "editing_note": "new",
            "default_type": "ticket",
            "default_ticket_key": ticket_key
        }
        st.rerun()

    # Recent notes count
    try:
        recent_notes = db_manager.get_notes()
        if recent_notes:
            recent_count = len([n for n in recent_notes
                                if (datetime.now() - datetime.fromisoformat(n['created_at'])).days <= 7])
            st.sidebar.metric("Notes This Week", recent_count)
    except:
        pass