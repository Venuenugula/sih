# INDUSAI — Industrial AI Workbench

Student prototype for Smart India Hackathon.

INDUSAI helps an engineer look at machine manuals, maintenance history, inspection images, and sensor CSV files, then ask questions using AI.

This is a **working demonstration**, not an enterprise product.

**External AI Inference — Prototype Mode**

Answers and image analysis use an **external** multimodal LLM API. This app does **not** run the LLM on-premises. A later version can swap that API for a locally hosted open-weight model.

---

## Primary demo

**Machine:** PUMP-204

**Files (to be added under `demo/` and `data/`):**

- `pump_manual.pdf`
- `maintenance_history.pdf`
- `inspection_procedure.pdf`
- `inspection.jpg`
- `sensor_data.csv`

**Question:**

> What should I inspect on this machine, and are there any abnormal sensor readings?

---

## How to run

If you have never used a terminal, API keys, or a database, read **[SETUP.md](SETUP.md)** first. It explains every command.

```bash
cd /home/rgukt-basar/sih
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env and paste your LLM_API_KEY (see SETUP.md)
streamlit run app.py
```

Open the local URL Streamlit prints (usually `http://localhost:8501`).

SQLite and ChromaDB files are created automatically on first run. You do not install PostgreSQL or Docker.

**Deploy (LAN, VPS, or Streamlit Cloud):** see **[DEPLOY.md](DEPLOY.md)**.

---

## Project layout

```
app.py                 Streamlit app
config.py              Settings from .env
llm.py                 External LLM calls
rag.py                 ChromaDB retrieval
documents.py           PDF text extraction
sensor_analysis.py     CSV checks and charts
image_analysis.py      Inspection image → vision model
agent.py               Gather evidence, then ask the LLM
auth.py                Simple login + department access
database.py            SQLite (users, audit, review)
report.py              PDF report (ReportLab)

data/documents/        Uploaded / demo PDFs
data/images/           Inspection images
data/sensors/          Sensor CSV files
data/reports/          Generated PDF reports
demo/                  Demo files for PUMP-204
chroma_db/             Local vector store
```

Python files above are implemented for the student demo.

---

## Demo flow

- Demo admin: `admin` / `demo123` (Maintenance)
- Demo engineer: `engineer` / `demo123` (Maintenance)
- Demo reviewer: `reviewer` / `demo123` (Maintenance)

Passwords are stored as hashes in SQLite. Login uses Streamlit session state only (no JWT).

1. Login (`engineer` / `demo123`)
2. Dashboard → **Prepare demo files**
3. Open an investigation for PUMP-204
4. Documents → search or reuse indexed PDFs
5. Analyze `sensor_data.csv` (Pandas/NumPy, not the LLM)
6. Analyze `inspection.jpg` with the external vision model (needs `.env` key)
7. Ask the demo question with **Generate answer** (needs `.env` key)
8. Show the AI answer, sources, and a PDF report
9. Human review (`reviewer` / `demo123`) + audit log

The LLM only receives evidence needed for the current question. It does not receive the whole database, unrelated files, passwords, or API keys.

---

## Tech stack

Python, Streamlit, PyMuPDF, ChromaDB, Sentence Transformers, Pandas, NumPy, Plotly, SQLite, ReportLab, external multimodal LLM API.

Not used: React, Next.js, FastAPI, PostgreSQL, Docker, Kubernetes, Redis, Qdrant, LangGraph, microservices.

---

## Notes

- Demo users and files are synthetic.
- Keep API keys in `.env` only.
- See [ARCHITECTURE.md](ARCHITECTURE.md) for a short system overview.
