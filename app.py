"""
Streamlit UI.

Lets you chat with any of several agent personas. Each (agent, session)
pair has its own private memory. When you hit "End session & consolidate",
the transcript is distilled into anonymized, general knowledge and merged
into the one shared knowledge base that every agent/session can draw on.
"""
import streamlit as st

import core.telemetry  # Initialize OpenTelemetry and auto-instrumentation
from opentelemetry import trace

from core.agents import AGENTS, DEFAULT_AGENT_ID
from core.extractor import extract_generalized_knowledge
from core.graph import build_graph
from core.private_memory import PrivateMemoryStore
from core.shared_knowledge import SharedKnowledgeStore

tracer = trace.get_tracer(__name__)

st.set_page_config(page_title="Shared Knowledge / Private Memory", page_icon="🧠", layout="wide")


@st.cache_resource
def get_stores():
    return PrivateMemoryStore(), SharedKnowledgeStore()


private_store, shared_store = get_stores()
graph = build_graph(private_store, shared_store)

if "agent_id" not in st.session_state:
    st.session_state.agent_id = DEFAULT_AGENT_ID
if "session_id" not in st.session_state:
    st.session_state.session_id = private_store.create_session(st.session_state.agent_id)

# ============================== Sidebar ==============================
with st.sidebar:
    st.title("🧠 Agents")

    agent_labels = {aid: cfg["name"] for aid, cfg in AGENTS.items()}
    chosen = st.selectbox(
        "Active agent",
        options=list(agent_labels.keys()),
        format_func=lambda x: agent_labels[x],
        index=list(agent_labels.keys()).index(st.session_state.agent_id),
    )
    if chosen != st.session_state.agent_id:
        st.session_state.agent_id = chosen
        st.session_state.session_id = private_store.create_session(chosen)
        st.rerun()

    st.caption(AGENTS[st.session_state.agent_id]["system_prompt"])

    st.divider()
    st.subheader("Session (private)")
    st.code(st.session_state.session_id[:8], language=None)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🆕 New session", use_container_width=True):
            st.session_state.session_id = private_store.create_session(st.session_state.agent_id)
            st.rerun()
    with col2:
        if st.button("🗑️ Delete", use_container_width=True):
            private_store.delete_session(st.session_state.session_id)
            st.session_state.session_id = private_store.create_session(st.session_state.agent_id)
            st.rerun()

    if st.button("📚 End session & consolidate to shared knowledge", use_container_width=True):
        messages = private_store.get_messages(st.session_state.session_id)
        with st.spinner("Distilling generalized knowledge (anonymized)..."):
            with tracer.start_as_current_span("consolidate_session") as span:
                span.set_attribute("agent_id", st.session_state.agent_id)
                span.set_attribute("session_id", st.session_state.session_id)
                snippets = extract_generalized_knowledge(messages)
                span.set_attribute("snippets_count", len(snippets))
                shared_store.add_knowledge(
                    snippets,
                    source_agent_id=st.session_state.agent_id,
                    topic=AGENTS[st.session_state.agent_id]["name"],
                )
                private_store.mark_consolidated(st.session_state.session_id)
        if snippets:
            st.success(f"Added {len(snippets)} generalized snippet(s) to shared knowledge.")
        else:
            st.info("Nothing generalizable found in this session.")

    st.divider()
    st.subheader(f"🌐 Shared knowledge ({shared_store.count()})")
    st.caption("Visible to every agent & session. Contains no personal details.")
    with st.expander("Browse shared knowledge base"):
        items = shared_store.all_knowledge(limit=50)
        if not items:
            st.caption("Empty so far — consolidate a session to add to it.")
        for item in items:
            st.markdown(f"- {item['content']}  \n  &nbsp;&nbsp;*— from {item['metadata'].get('topic', 'general')}*")

# ============================== Main chat ==============================
st.title(AGENTS[st.session_state.agent_id]["name"])
st.caption(
    "Answers use this session's private memory (this conversation only) plus "
    "generalized knowledge shared across all agents and sessions."
)

history = private_store.get_messages(st.session_state.session_id)
for m in history:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

user_input = st.chat_input("Ask something...")
if user_input:
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            with tracer.start_as_current_span("chat_turn") as span:
                span.set_attribute("agent_id", st.session_state.agent_id)
                span.set_attribute("session_id", st.session_state.session_id)
                span.set_attribute("user_input", user_input)
                result = graph.invoke(
                    {
                        "session_id": st.session_state.session_id,
                        "agent_id": st.session_state.agent_id,
                        "user_input": user_input,
                        "private_history": [],
                        "shared_context": [],
                        "response": "",
                    }
                )
                span.set_attribute("agent_response", result["response"])
            st.markdown(result["response"])

            with st.expander("🔍 Shared knowledge used for this answer"):
                if result["shared_context"]:
                    for r in result["shared_context"]:
                        st.markdown(f"- {r['content']}")
                else:
                    st.caption("No relevant shared knowledge retrieved.")
