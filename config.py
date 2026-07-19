"""
Central configuration: which LLM/embedding providers to use, and where
data lives on disk. Everything is driven by environment variables so the
same code runs with Anthropic or OpenAI, and with local or hosted embeddings.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# --- LLM (chat) provider ---------------------------------------------------
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "anthropic").lower()  # "anthropic" | "openai"
LLM_MODEL = os.getenv(
    "LLM_MODEL",
    "claude-sonnet-4-6" if LLM_PROVIDER == "anthropic" else "gpt-4o-mini",
)

# --- Embeddings provider (used only for the shared knowledge vector store) -
# Defaults to a local, free HuggingFace model so the project runs with just
# an Anthropic key and no second API key required.
EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "huggingface").lower()  # "huggingface" | "openai"
EMBEDDING_MODEL = os.getenv(
    "EMBEDDING_MODEL",
    "sentence-transformers/all-MiniLM-L6-v2" if EMBEDDING_PROVIDER == "huggingface" else "text-embedding-3-small",
)

# --- Storage -----------------------------------------------------------
DATA_DIR = os.getenv("DATA_DIR", os.path.join(os.path.dirname(__file__), "data"))
PRIVATE_DB_PATH = os.path.join(DATA_DIR, "private_memory.db")
SHARED_KB_DIR = os.path.join(DATA_DIR, "shared_knowledge")


def get_llm(temperature: float = 0.4):
    """Return a LangChain chat model instance for the configured provider."""
    if LLM_PROVIDER == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model=LLM_MODEL, temperature=temperature)
    elif LLM_PROVIDER == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=LLM_MODEL, temperature=temperature)
    raise ValueError(f"Unsupported LLM_PROVIDER: {LLM_PROVIDER!r} (use 'anthropic' or 'openai')")


def get_embeddings():
    """Return a LangChain embeddings instance for the configured provider."""
    if EMBEDDING_PROVIDER == "huggingface":
        from langchain_huggingface import HuggingFaceEmbeddings
        return HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
    elif EMBEDDING_PROVIDER == "openai":
        from langchain_openai import OpenAIEmbeddings
        return OpenAIEmbeddings(model=EMBEDDING_MODEL)
    raise ValueError(f"Unsupported EMBEDDING_PROVIDER: {EMBEDDING_PROVIDER!r} (use 'huggingface' or 'openai')")
