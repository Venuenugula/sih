# INDUSAI architecture (prototype)

Simple one-app design for a student demo.

```
Engineer (browser)
        |
        v
  Streamlit  (app.py)
        |
        +-- auth.py          login, department access
        +-- database.py      SQLite: users, investigations, audit, review
        +-- documents.py     PDF text with PyMuPDF
        +-- rag.py           chunk + embed + ChromaDB search
        +-- sensor_analysis.py   CSV stats / flags / Plotly
        +-- image_analysis.py    send image + short prompt to vision API
        +-- agent.py         collect only relevant evidence
        +-- llm.py           call external multimodal LLM
        +-- report.py        write a PDF with ReportLab
```

Run command: `streamlit run app.py`

There is no separate API server, no Docker, and no microservices.

---

## What runs locally

| Piece | Role |
| --- | --- |
| Streamlit | UI and all feature logic |
| SQLite | Login, departments, audit log, human review |
| PyMuPDF | Extract text from PDFs |
| Sentence Transformers | Embeddings on this machine |
| ChromaDB | Store and search document chunks |
| Pandas / NumPy / Plotly | Sensor CSV analysis and charts |
| ReportLab | Downloadable PDF report |

---

## What is external

| Piece | Role |
| --- | --- |
| Multimodal LLM API | Answer the question and describe inspection images |

**External AI Inference — Prototype Mode**

The LLM is not on-premises. Do not describe this prototype as an on-prem or air-gapped AI system.

Later, `llm.py` can point at a locally hosted open-weight model instead of the cloud API. The rest of the app stays the same.

---

## Evidence sent to the LLM

For each question, `agent.py` should send only:

- the question
- a few retrieved PDF chunks (RAG top-k)
- a short sensor summary (not the full CSV unless it is tiny)
- a vision-model caption or the one inspection image for the current machine

Do not send:

- the full ChromaDB store
- unrelated manuals
- other machines’ files
- passwords, API keys, or raw audit tables

---

## Simple access control

Demo users belong to a department (for example Maintenance).

A user can open files and investigations for their department. This is a basic check in SQLite, not a full security product.

---

## Data for the PUMP-204 demo

```
demo/  and  data/
  pump_manual.pdf
  maintenance_history.pdf
  inspection_procedure.pdf
  inspection.jpg
  sensor_data.csv
```

All of this is synthetic.

---

## File responsibilities (to implement later)

| File | Job |
| --- | --- |
| `app.py` | Pages: login, dashboard, investigation |
| `config.py` | Read `.env` |
| `llm.py` | HTTP call to the external LLM |
| `rag.py` | Embed, store, retrieve chunks |
| `documents.py` | PDF upload + text extraction |
| `sensor_analysis.py` | CSV anomalies + charts |
| `image_analysis.py` | Image → vision model |
| `agent.py` | Build a small evidence pack, then ask `llm.py` |
| `auth.py` | Login and department check |
| `database.py` | SQLite helpers |
| `report.py` | PDF report from the investigation |

---

## What this prototype is not

Not a production plant system. Not on-premises LLM inference. Not a multi-service platform.
