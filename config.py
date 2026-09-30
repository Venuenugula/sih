"""Load settings from .env. Safe defaults so the app runs without a local .env."""

from pathlib import Path
import os

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")


def _apply_streamlit_secrets() -> None:
    """Streamlit Community Cloud / secrets.toml → same env vars as .env."""
    try:
        import streamlit as st

        keys = (
            "APP_NAME",
            "LLM_API_BASE_URL",
            "LLM_API_KEY",
            "LLM_MODEL",
            "VISION_MODEL",
            "LLM_TIMEOUT_SECONDS",
            "EMBEDDING_MODEL",
            "CHROMA_PATH",
            "SQLITE_PATH",
            "DATA_DIR",
            "DEMO_ADMIN_USERNAME",
            "DEMO_ADMIN_PASSWORD",
            "DEMO_ENGINEER_USERNAME",
            "DEMO_ENGINEER_PASSWORD",
            "DEMO_REVIEWER_USERNAME",
            "DEMO_REVIEWER_PASSWORD",
        )
        for key in keys:
            if key in st.secrets:
                os.environ[key] = str(st.secrets[key])
    except Exception:
        return


_apply_streamlit_secrets()

APP_NAME = os.getenv("APP_NAME", "INDUSAI")
APP_MODE = os.getenv("APP_MODE", "prototype")
AI_INFERENCE_LABEL = os.getenv(
    "AI_INFERENCE_LABEL",
    "External AI Inference — Prototype Mode",
)

DATA_DIR = Path(os.getenv("DATA_DIR", ROOT / "data"))
DOCUMENTS_DIR = DATA_DIR / "documents"
IMAGES_DIR = DATA_DIR / "images"
SENSORS_DIR = DATA_DIR / "sensors"
REPORTS_DIR = DATA_DIR / "reports"
DEMO_DIR = ROOT / "demo"
SQLITE_PATH = Path(os.getenv("SQLITE_PATH", DATA_DIR / "indusai.sqlite"))

DEMO_ADMIN_USERNAME = os.getenv("DEMO_ADMIN_USERNAME", "admin")
DEMO_ADMIN_PASSWORD = os.getenv("DEMO_ADMIN_PASSWORD", "demo123")
DEMO_ENGINEER_USERNAME = os.getenv("DEMO_ENGINEER_USERNAME", "engineer")
DEMO_ENGINEER_PASSWORD = os.getenv("DEMO_ENGINEER_PASSWORD", "demo123")
DEMO_REVIEWER_USERNAME = os.getenv("DEMO_REVIEWER_USERNAME", "reviewer")
DEMO_REVIEWER_PASSWORD = os.getenv("DEMO_REVIEWER_PASSWORD", "demo123")

CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "500"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "50"))
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "5"))
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
CHROMA_PATH = Path(os.getenv("CHROMA_PATH", ROOT / "chroma_db"))

LLM_API_BASE_URL = (os.getenv("LLM_API_BASE_URL") or "").rstrip("/")
LLM_API_KEY = os.getenv("LLM_API_KEY") or ""
LLM_MODEL = os.getenv("LLM_MODEL") or ""
VISION_MODEL = os.getenv("VISION_MODEL") or LLM_MODEL
LLM_TIMEOUT_SECONDS = int(os.getenv("LLM_TIMEOUT_SECONDS", "60"))

# Primary SIH demo asset
DEMO_MACHINE_ID = "PUMP-204"
DEMO_PDF_NAME = "pump_manual.pdf"
DEMO_IMAGE_NAME = "inspection.jpg"

_PLACEHOLDER_KEYS = {
    "",
    "replace-with-your-key",
    "your_api_key_here",
    "changeme",
}


def llm_key_configured() -> bool:
    """True when a non-placeholder key is present. Never prints the key."""
    return LLM_API_KEY.strip() not in _PLACEHOLDER_KEYS


def vision_configured() -> bool:
    return bool(LLM_API_BASE_URL) and bool(VISION_MODEL) and llm_key_configured()


def llm_configured() -> bool:
    return bool(LLM_API_BASE_URL) and bool(LLM_MODEL) and llm_key_configured()


def ensure_folders() -> None:
    for folder in (DOCUMENTS_DIR, IMAGES_DIR, SENSORS_DIR, REPORTS_DIR, DEMO_DIR, CHROMA_PATH):
        folder.mkdir(parents=True, exist_ok=True)
