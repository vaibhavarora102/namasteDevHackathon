"""
LangGraph agent.

Per turn, the graph:
  1. retrieves relevant snippets from the SHARED knowledge base (cross-session, anonymized)
  2. loads this session's PRIVATE history (this conversation only)
  3. generates a response using both
  4. persists the new turn back into private memory only

Consolidation (private -> shared) is a separate, explicit step
(see extractor.py) -- it does NOT happen automatically on every turn, so
raw private content is never silently pushed into the shared store.
"""
from typing import Dict, List, TypedDict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph

from config import get_llm
from core.agents import AGENTS
from core.private_memory import PrivateMemoryStore
from core.shared_knowledge import SharedKnowledgeStore


class AgentState(TypedDict):
    session_id: str
    agent_id: str
    user_input: str
    private_history: List[Dict]
    shared_context: List[Dict]
    response: str


def build_graph(private_store: PrivateMemoryStore, shared_store: SharedKnowledgeStore):
    def retrieve_shared_knowledge(state: AgentState) -> AgentState:
        state["shared_context"] = shared_store.query(state["user_input"], k=4)
        return state

    def load_private_memory(state: AgentState) -> AgentState:
        state["private_history"] = private_store.get_messages(state["session_id"])
        return state

    def generate_response(state: AgentState) -> AgentState:
        agent_cfg = AGENTS.get(state["agent_id"], AGENTS["research_assistant"])
        llm = get_llm()

        shared_snippets = "\n".join(f"- {r['content']}" for r in state["shared_context"])
        shared_snippets = shared_snippets or "(no relevant shared knowledge yet)"

        system_text = (
            f"{agent_cfg['system_prompt']}\n\n"
            "You have access to generalized knowledge distilled from many past sessions, "
            "across all users and agents. It contains no information about who said what "
            "-- treat it as background expertise, not memory of this specific user. "
            "Use it only if relevant.\n\n"
            f"Relevant shared knowledge:\n{shared_snippets}"
        )

        lc_messages = [SystemMessage(content=system_text)]
        for m in state["private_history"]:
            if m["role"] == "user":
                lc_messages.append(HumanMessage(content=m["content"]))
            else:
                lc_messages.append(AIMessage(content=m["content"]))
        lc_messages.append(HumanMessage(content=state["user_input"]))

        ai_msg = llm.invoke(lc_messages)
        state["response"] = ai_msg.content
        return state

    def persist_turn(state: AgentState) -> AgentState:
        private_store.add_message(state["session_id"], "user", state["user_input"])
        private_store.add_message(state["session_id"], "assistant", state["response"])
        return state

    graph = StateGraph(AgentState)
    graph.add_node("retrieve_shared_knowledge", retrieve_shared_knowledge)
    graph.add_node("load_private_memory", load_private_memory)
    graph.add_node("generate_response", generate_response)
    graph.add_node("persist_turn", persist_turn)

    graph.set_entry_point("retrieve_shared_knowledge")
    graph.add_edge("retrieve_shared_knowledge", "load_private_memory")
    graph.add_edge("load_private_memory", "generate_response")
    graph.add_edge("generate_response", "persist_turn")
    graph.add_edge("persist_turn", END)

    return graph.compile()
