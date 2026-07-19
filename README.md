# Shared Knowledge / Private Memory Agents

**🔴 Live demo:** [namastedevhackathon-p8avfpywoxccw3nfeggs7e.streamlit.app](https://namastedevhackathon-p8avfpywoxccw3nfeggs7e.streamlit.app/)
**📦 Repo:** [github.com/vaibhavarora102/namasteDevHackathon](https://github.com/vaibhavarora102/namasteDevHackathon)

Built for the [OpenAI × NamasteDev Codex Hackathon](https://namastedev.com/hackathon) (July 2026).

## The 10-second pitch

AI agents that remember everything either leak private data across sessions, or
forget everything and never improve — there's rarely a middle ground. This project
is a working pattern for that middle ground: every chat session has **fully
private memory**, but when a session ends, an LLM distills it into short,
**anonymized, generalized lessons**, and *only* those lessons are shared across
every other agent persona and every future session. No agent ever reads another
session's raw transcript — the anonymization step is explicit, visible, and
auditable, not something happening silently in the background.

Three agent personas (Coding Tutor, Research Assistant, Wellness Coach) share one
knowledge base but never share raw conversations — try it live: teach the Coding
Tutor a debugging tip, consolidate the session, then ask the Research Assistant a
related question and watch it retrieve that same lesson, stripped of anything
personal.

A small multi-agent chat system built with **LangChain + LangGraph + Streamlit** that
demonstrates a specific memory pattern:

> Agents learn from one session to the next — but only *generalized, anonymized
> knowledge*, never the private details of who said what.

Each chat session has its own **private memory** (the raw conversation transcript,
which may contain names, specifics, anything personal). When a session ends, an
LLM-based **consolidation step** distills that transcript into short, impersonal
"lessons" (facts, strategies, corrections) and merges them into a single **shared
knowledge base**. Every agent persona and every future session can then draw on
that shared knowledge base — but none of them can ever see another session's raw
private memory.

```
  +--------------------------------------+
  |      Coding Tutor -- Session A       |
  +--------------------------------------+
                      |
           raw chat, every turn
                      v
  +--------------------------------------+
  |       PRIVATE MEMORY  (SQLite)       |
  |      per-session, never shared       |
  +--------------------------------------+
                      |
       "End session & consolidate"
                      v
  +--------------------------------------+
  |           EXTRACTOR  (LLM)           |
  |        anonymize + generalize        |
  +--------------------------------------+
                      |
         generalized lessons only
                      v
  +--------------------------------------+
  |      SHARED KNOWLEDGE  (Chroma)      |
  |        global, RAG-searchable        |
  +--------------------------------------+
                      |
    semantic retrieval at answer time
                      v
  +--------------------------------------+
  |   Research Assistant -- Session B    |
  | different agent, brand-new session,  |
  | never saw Session A's raw transcript |
  +--------------------------------------+
```

## What this demonstrates

- **Private memory** — a SQLite-backed store keyed by `session_id`. Holds the raw
  back-and-forth of one conversation. Deletable on demand.
- **Shared knowledge** — a Chroma vector store holding short, generalized,
  anonymized snippets, retrievable by any agent via semantic search (RAG).
- **The one-way bridge** — the *only* path from private → shared is an LLM
  extraction step with an explicit anonymization prompt (see
  `core/extractor.py`). It is a deliberate, visible step, not something that
  happens silently on every turn.
- **Multiple agent personas** sharing one knowledge base — a "Coding Tutor" and
  a "Research Assistant" have separate private memories but both read/write the
  same shared knowledge, so a lesson learned in one persona's session can help
  another persona later.

## Project layout

```
knowledge-share-private-memory/
├── app.py                    # Streamlit chat UI (entry point)
├── config.py                 # LLM / embeddings provider config
├── core/
│   ├── agents.py             # Agent persona definitions
│   ├── private_memory.py     # Per-session private memory (SQLite)
│   ├── shared_knowledge.py   # Shared knowledge base (Chroma)
│   ├── extractor.py          # private -> shared consolidation (LLM + anonymization)
│   └── graph.py              # LangGraph state machine wiring it together
├── data/                     # created at runtime (sqlite db + chroma dir)
├── requirements.txt
├── .env.example
└── docs/
    └── IMPLEMENTATION.md     # deeper technical write-up
```

## Setup

**1. Clone / copy the project and create a virtualenv (recommended):**

```bash
cd knowledge-share-private-memory
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
```

**2. Install dependencies:**

```bash
pip install -r requirements.txt
```

> Note: the default embedding provider (`huggingface`, via `sentence-transformers`)
> pulls in `torch`, which is a large download. If you'd rather avoid that, set
> `EMBEDDING_PROVIDER=openai` in `.env` (see below) and it'll use OpenAI
> embeddings instead — you'll just need an `OPENAI_API_KEY` either way in that case.

**3. Configure environment variables:**

```bash
cp .env.example .env
```

Edit `.env`:

```ini
LLM_PROVIDER=anthropic          # or "openai"
LLM_MODEL=claude-sonnet-4-6     # or e.g. "gpt-4o-mini"
ANTHROPIC_API_KEY=sk-ant-...    # set the key matching LLM_PROVIDER
OPENAI_API_KEY=sk-...

EMBEDDING_PROVIDER=huggingface  # local/free, no key needed. or "openai"
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2

DATA_DIR=data
```

You only need to set the API key that matches `LLM_PROVIDER` (plus an OpenAI key
too, if you also set `EMBEDDING_PROVIDER=openai`).

## Run

```bash
streamlit run app.py
```

Open the URL Streamlit prints (usually `http://localhost:8501`).

## 60-second test (for judges)

Try this directly on the [live demo](https://namastedevhackathon-p8avfpywoxccw3nfeggs7e.streamlit.app/) — no setup needed:

1. Select **Coding Tutor** in the sidebar. Send: *"Hey, I'm stuck — my async
   function hangs because I'm calling `time.sleep()` inside `async def` instead
   of `await asyncio.sleep()`."*
2. Click **"📚 End session & consolidate to shared knowledge"**. Open the
   shared knowledge expander — the lesson is there, but your identity/phrasing
   is gone, replaced by an impersonal, reusable statement.
3. Switch to **Research Assistant** (a brand-new, unrelated private session)
   and ask: *"Why would an async Python function never return control?"*
   Check the **"🔍 Shared knowledge used for this answer"** expander — it
   retrieved the same lesson the Coding Tutor session produced, without ever
   seeing that transcript.

That round trip — private conversation → anonymized distillation → cross-agent
retrieval — is the whole idea.

## Using the app

1. **Pick an agent persona** in the sidebar (Research Assistant / Coding Tutor /
   Wellness Coach). Switching personas starts a fresh private session.
2. **Chat normally.** Each reply is generated using this session's private
   history *plus* any relevant snippets retrieved from the shared knowledge
   base (shown in a "Shared knowledge used for this answer" expander under
   each response).
3. **Click "New session"** to start a new private conversation with the same
   agent (e.g. simulate a different day, or a different person talking to the
   same assistant).
4. **Click "End session & consolidate to shared knowledge"** when you're done
   with a conversation. This runs the extraction step, which reads the private
   transcript and asks the LLM to output only generalized, anonymized
   knowledge — dropping anything person-specific. Whatever comes back is
   embedded and added to the shared knowledge base.
5. **Browse the shared knowledge base** in the sidebar expander to see exactly
   what has been "learned" so far, and confirm it stays free of personal
   specifics.
6. **Try it cross-agent:** consolidate a Coding Tutor session that contains a
   generalizable debugging tip, then switch to the Research Assistant and ask
   a related question — you should see the same tip retrieved there.

## A note on the privacy guarantee

This project demonstrates the *pattern*, not a certified privacy system. The
anonymization boundary is enforced by an LLM prompt (`core/extractor.py`), which
is a reasonable line of defense but not infallible — a sufficiently unusual
transcript could still leak something specific if the model doesn't follow
instructions perfectly. For a production system you'd want to add deterministic
safeguards on top (e.g. PII regex/NER filtering on extracted snippets before
they're written to the shared store, human review, or a second LLM pass that
scores/vetoes candidate snippets). See `docs/IMPLEMENTATION.md` for more on
this and other extension ideas.
