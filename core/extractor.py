"""
Consolidation / reflection step.

Turns a private session transcript into a short list of *generalized,
anonymized* knowledge snippets that are safe to add to the shared
knowledge base. This is the only bridge between private memory and
shared knowledge, and it is deliberately narrow and instruction-guarded.
"""
import json
import re
from typing import Dict, List

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from config import get_llm

EXTRACTION_SYSTEM_PROMPT = """You distill a private conversation transcript into general, reusable \
knowledge for a shared knowledge base that other agents and future sessions can draw on.

Rules (follow strictly):
1. Output ONLY generalizable knowledge: facts about the world, correct answers, useful strategies, \
recurring mistakes and their fixes, domain tips, or stylistic lessons stated as general rules.
2. NEVER include names, emails, phone numbers, addresses, IDs, employers, exact dates tied to a \
person, or any other detail that identifies or describes the specific individual in the conversation.
3. NEVER include one-off personal facts (e.g. "the user's dog is named Max"). If a fact is only \
useful for personalizing replies to this one person, DROP it -- it belongs in private memory, not here.
4. Rephrase everything as an impersonal, standalone statement usable in a different conversation \
with a different person, e.g. "When users ask about X, approach Y works well" rather than \
"I told the user that Y works well".
5. If nothing in the transcript is worth generalizing, return an empty array.
6. Return STRICT JSON only: a JSON array of strings. No prose, no markdown fences, no commentary.

Example output:
["Users asking about async/await bugs in Python often actually have a blocking call inside a \
coroutine; check for that first.", "For budget travel questions, mentioning shoulder-season dates \
is usually the highest-leverage tip."]
"""

_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", EXTRACTION_SYSTEM_PROMPT),
        ("human", "Transcript:\n\n{transcript}\n\nReturn the JSON array now."),
    ]
)


def _format_transcript(messages: List[Dict]) -> str:
    lines = []
    for m in messages:
        role = "User" if m["role"] == "user" else "Assistant"
        lines.append(f"{role}: {m['content']}")
    return "\n".join(lines)


def _parse_json_array(raw: str) -> List[str]:
    cleaned = raw.strip()
    cleaned = re.sub(r"^```(json)?|```$", "", cleaned, flags=re.MULTILINE).strip()
    try:
        data = json.loads(cleaned)
        if isinstance(data, list):
            return [str(x).strip() for x in data if str(x).strip()]
    except json.JSONDecodeError:
        pass
    return []


def extract_generalized_knowledge(messages: List[Dict]) -> List[str]:
    """Given a private session's messages, return a list of anonymized,
    generalized knowledge snippets safe to store in the shared knowledge base.
    Returns an empty list if there's nothing worth generalizing.
    """
    if not messages:
        return []
    llm = get_llm(temperature=0.0)
    chain = _prompt | llm | StrOutputParser()
    raw = chain.invoke({"transcript": _format_transcript(messages)})
    return _parse_json_array(raw)
