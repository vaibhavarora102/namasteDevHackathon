# Implementation Notes

This document describes what is actually implemented right now, the design
decisions behind it, and what a next iteration could add.

## 1. Memory model

There are exactly two stores, and the boundary between them is the core idea
of the project.

### 1.1 Private memory (`core/private_memory.py`)

- Backing store: SQLite (`data/private_memory.db`).
- Schema:
  - `sessions(session_id, agent_id, created_at, consolidated)`
  - `messages(id, session_id, role, content, created_at)`
- Scope: one row set per `session_id`. A session belongs to exactly one
  agent persona (`agent_id`) and is never read by any other session, even
  sessions of the same persona.
- Lifecycle: created when a chat starts (`create_session`), appended to on
  every turn (`add_message`), optionally flagged `consolidated=1` after
  extraction runs, and deletable in full (`delete_session`) — e.g. for a
  "forget this conversation" control.
- Nothing in this module ever touches the shared store. It has no import of
  `shared_knowledge.py`. That's intentional — private memory code should be
  incapable of leaking into the shared store by accident.

### 1.2 Shared knowledge (`core/shared_knowledge.py`)

- Backing store: Chroma, persisted to `data/shared_knowledge/`.
- Each entry is a short text snippet + metadata: `source_agent_id` (which
  persona contributed it — for traceability, not personalization),
  `topic`, `created_at`, `knowledge_id`.
- Read via semantic search (`query`, top-k similarity) at answer time, and
  via `all_knowledge()` for the sidebar browser in the UI.
- Explicitly global: one Chroma collection, no per-agent or per-session
  partitioning. Every agent persona and every session queries the same
  collection. This is what makes "agent B benefits from something agent A's
  session taught it" possible.

### 1.3 The bridge: consolidation (`core/extractor.py`)

This is the only code path allowed to move information from private memory
into shared knowledge, and it's a distinct, visible action (a sidebar
button in the UI), not an automatic per-turn side effect.

`extract_generalized_knowledge(messages)`:
1. Formats the private transcript as plain `User: ... / Assistant: ...` text.
2. Sends it to the LLM with a system prompt that:
   - asks for generalizable knowledge only (facts, strategies, recurring
     fixes, domain tips),
   - explicitly forbids names, contact info, employers, personal dates, or
     any one-off fact tied to a specific individual,
   - requires rephrasing into impersonal, standalone statements,
   - allows (and expects) an **empty result** when nothing is generalizable
     — not every conversation contains reusable knowledge, and that's fine,
   - constrains output format to a strict JSON array of strings (no prose),
     so it can be parsed reliably.
3. Parses the JSON defensively (`_parse_json_array`): strips markdown code
   fences if the model adds them anyway, and fails safe to `[]` on anything
   that isn't valid JSON, rather than guessing.
4. The caller (`app.py`) takes the returned list and calls
   `shared_store.add_knowledge(snippets, source_agent_id, topic)`.

This is a **prompt-level privacy boundary**, not a cryptographic or
deterministic one — see §4 for how to harden it.

## 2. Agent orchestration (`core/graph.py`, LangGraph)

A single `StateGraph` with four nodes, run once per user turn:

```
retrieve_shared_knowledge → load_private_memory → generate_response → persist_turn
```

- **`retrieve_shared_knowledge`**: semantic search over the shared Chroma
  store using the user's latest message as the query. Top-4 by default.
- **`load_private_memory`**: reads this session's full prior transcript from
  SQLite.
- **`generate_response`**: builds a system prompt combining the agent
  persona's base instructions with the retrieved shared snippets (explicitly
  labeled as "background expertise, not memory of this specific user" so the
  model doesn't treat it as if it knows the current person), then calls the
  chat LLM with the private history + new user message.
- **`persist_turn`**: writes the new user/assistant turn back to private
  memory *only*.

State shape (`AgentState`, a `TypedDict`):

```python
{
  "session_id": str,
  "agent_id": str,
  "user_input": str,
  "private_history": list[dict],   # populated by load_private_memory
  "shared_context": list[dict],    # populated by retrieve_shared_knowledge
  "response": str,                 # populated by generate_response
}
```

The graph is intentionally linear (no branching/looping) since one chat turn
is a simple pipeline. It's still built as a LangGraph `StateGraph` rather
than a plain function chain so it's easy to extend — e.g. add a conditional
edge that skips shared-knowledge retrieval for very short/greeting messages,
or add a branch that runs a safety check before `generate_response`.

## 3. Agent personas (`core/agents.py`)

Three example personas (`research_assistant`, `coding_tutor`,
`wellness_coach`), each just a `name` + `system_prompt`. They share:
- the same LangGraph pipeline,
- the same shared knowledge base,
- but separate, independent private-memory sessions.

This is what demonstrates *cross-agent* knowledge transfer: consolidate a
`coding_tutor` session, then ask the `research_assistant` a related
question — it can retrieve the same shared snippet, without ever having
access to the coding_tutor session's transcript.

Adding a new persona is a one-entry addition to the `AGENTS` dict; nothing
else needs to change.

## 4. Ideas for hardening / extending

These aren't implemented, but the architecture is set up to support them:

- **Deterministic PII filtering as defense-in-depth.** Run extracted
  snippets through a regex/NER-based PII scrubber (e.g. `presidio`) before
  `add_knowledge`, in addition to the prompt-level instruction, so a
  prompt-injection or model mistake doesn't leak something.
- **A second "critic" LLM pass** that scores each candidate snippet for
  "is this generalizable / anonymized?" and drops low-confidence ones,
  rather than trusting a single extraction call.
- **Periodic/automatic consolidation** (e.g. after N turns or on a timer)
  instead of only a manual button — would need care to still keep it an
  explicit, auditable step (e.g. log what was extracted).
- **Knowledge decay / dedup.** Right now shared knowledge only grows.
  You could periodically cluster/deduplicate near-identical snippets, or
  decay/reweight old ones.
- **Per-topic shared collections** instead of one global collection, if you
  want e.g. "coding knowledge" and "wellness knowledge" to stay separate
  even though they're both "shared."
- **Human-in-the-loop review** of extracted snippets before they're
  committed to the shared store (approve/reject in the UI).
- **Swap SQLite for Postgres / Chroma for a hosted vector DB** for a
  multi-user deployment; the store classes (`PrivateMemoryStore`,
  `SharedKnowledgeStore`) are already isolated behind small interfaces so
  the swap wouldn't touch `graph.py` or `app.py`.

## 5. Testing notes

The core logic was verified with unit-level checks (not shipped as a test
suite, but reproducible):
- `PrivateMemoryStore`: create/add/get/list/delete session round-trips.
- `SharedKnowledgeStore`: add/query/all_knowledge/count round-trips (using a
  fake embeddings model to avoid requiring API keys / large downloads).
- `extractor._parse_json_array`: valid JSON, markdown-fenced JSON, empty
  array, and non-JSON garbage (fails safe to `[]`).
- Full `graph.py` pipeline: run end-to-end with a fake chat model and fake
  embeddings, confirming shared context is retrieved and injected into the
  prompt, and that only the private store is written to after a turn.

To exercise it for real, you need a live `ANTHROPIC_API_KEY` or
`OPENAI_API_KEY` (see `README.md`).
