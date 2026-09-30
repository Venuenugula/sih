# INDUSAI beginner setup guide

This file is for a teammate who has **never used a terminal, API keys, or a database**.

Follow the steps **in order**. Copy each command exactly. Press **Enter** after each line.

Your computer already has **Python 3.10**. You do **not** need Docker, PostgreSQL, or Node.js for this prototype.

---

## 0. What this project is (30 seconds)

INDUSAI is one Python app. You start it with:

```bash
streamlit run app.py
```

It opens in the browser at `http://localhost:8501`.

| Piece | What it is | Do you install a server? |
| --- | --- | --- |
| Streamlit | The website UI | No — Python package |
| SQLite | Login, audit log, reviews | No — one file on disk |
| ChromaDB | Search inside PDFs | No — a folder on disk |
| External LLM | Answers + image analysis | Yes — you need an **API key** |

The banner must stay: **External AI Inference — Prototype Mode**. Do not tell judges this LLM runs on your laptop.

---

## 1. Open a terminal

1. Click the **Terminal** panel at the bottom of Cursor (or press `` Ctrl+` ``).
2. You should see a line ending with `$`. That is the prompt. Type after it.

**Words you will see**

| Word | Meaning |
| --- | --- |
| `cd` | Change directory (go into a folder) |
| `ls` | List files in the current folder |
| `cp` | Copy a file |
| `nano` | Simple text editor inside the terminal |
| `source` | Turn on the Python virtual environment |
| `.venv` | A private Python install for this project only |

Go to the project folder:

```bash
cd /home/rgukt-basar/sih
```

Check you are in the right place:

```bash
ls
```

You should see `app.py`, `requirements.txt`, and `.env.example`.

---

## 2. Create a virtual environment (do this once)

A virtual environment keeps INDUSAI packages away from the rest of the computer.

```bash
python3 -m venv .venv
```

Turn it on (**every time** you open a new terminal):

```bash
source .venv/bin/activate
```

When it is on, the prompt starts with `(.venv)`.

Turn it off later (optional):

```bash
deactivate
```

---

## 3. Install Python packages (do this once, or after `requirements.txt` changes)

Make sure `(.venv)` is visible, then:

```bash
pip install -r requirements.txt
```

This can take several minutes. The first install of `sentence-transformers` may download extra files later when the app first embeds a PDF.

If you see `pip: command not found`, you forgot `source .venv/bin/activate`.

---

## 4. Create your secret file (`.env`)

`.env.example` is a **template**. It is safe to commit.  
`.env` is **your real secrets**. Never put it on GitHub.

Create `.env` from the template:

```bash
cp .env.example .env
```

Open it:

```bash
nano .env
```

- Move with arrow keys.
- Edit the values listed below.
- Save: `Ctrl+O`, then Enter.
- Quit: `Ctrl+X`.

You can also open `.env` in Cursor’s file tree (it may be hidden; use the command above if you cannot see it).

---

## 5. API keys — what to fill in

You need **one** multimodal LLM provider. The app talks to it over the internet.

Recommended for students (free tier): **Groq**.

### Option A — Groq (recommended)

1. Open https://console.groq.com in a browser.
2. Sign up / log in.
3. Open **API Keys** → **Create API Key**.
4. Copy the key **once**. You will not see it again. Paste it into `.env`.

In `.env` set:

```
LLM_API_BASE_URL=https://api.groq.com/openai/v1
LLM_API_KEY=gsk_paste_your_real_key_here
LLM_MODEL=llama-3.3-70b-versatile
VISION_MODEL=llama-3.2-11b-vision-preview
```

If Groq renamed a model, open their model list and paste the current **vision** model name into `VISION_MODEL` and a **text** model into `LLM_MODEL`.

### Option B — Google Gemini

1. Open https://aistudio.google.com/apikey
2. Create an API key.

Gemini’s HTTP path is not identical to OpenAI. Use Groq unless the builder has already added a Gemini client in `llm.py`. If they did, they will tell you the exact `.env` lines.

### Option C — OpenAI (paid)

```
LLM_API_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=sk-your-key
LLM_MODEL=gpt-4o-mini
VISION_MODEL=gpt-4o-mini
```

### Rules

- Never paste the key into chat, README, or GitHub.
- Never put the key inside `app.py`.
- Phase 1 (UI only) can run **without** a working key. You need the key when RAG / AI is implemented.

**You need the key for:** Analyse image, and **Generate answer**.

Login, PDFs, search, sensor charts, review, and PDF reports work **without** a key.

Leave these as they are unless a mentor tells you to change them:

```
EMBEDDING_MODEL=all-MiniLM-L6-v2
CHROMA_PATH=./chroma_db
SQLITE_PATH=./data/indusai.sqlite
DEMO_ADMIN_USERNAME=admin
DEMO_ADMIN_PASSWORD=demo123
DEMO_ENGINEER_USERNAME=engineer
DEMO_ENGINEER_PASSWORD=demo123
DEMO_REVIEWER_USERNAME=reviewer
DEMO_REVIEWER_PASSWORD=demo123
```

---

## 6. Database initialization (SQLite)

You do **not** install MySQL, PostgreSQL, or Docker for this prototype.

SQLite is a single file:

```
/home/rgukt-basar/sih/data/indusai.sqlite
```

**How it gets created**

When `database.py` is implemented, the app will:

1. Create the `data/` folder if needed.
2. Create `indusai.sqlite` on first launch.
3. Create tables: users, investigations, audit log, reviews.
4. Insert the two demo users from `.env`.

You should **not** run `psql`, `createdb`, or `docker compose` for INDUSAI.

**Reset the database** (wipes login/audit demo data; does not delete your PDFs):

```bash
rm -f /home/rgukt-basar/sih/data/indusai.sqlite
```

Then start the app again. It will recreate the file.

**ChromaDB** (PDF search index) is the folder `chroma_db/`. It is also created automatically. To wipe the search index only:

```bash
rm -rf /home/rgukt-basar/sih/chroma_db/*
```

Keep the folder itself.

---

## 7. Run the app

Every new terminal:

```bash
cd /home/rgukt-basar/sih
source .venv/bin/activate
streamlit run app.py
```

Wait until you see something like:

```
Local URL: http://localhost:8501
```

Open that URL in Chrome/Firefox.

Stop the app: click the terminal, then `Ctrl+C`.

---

## 8. Demo login (after Phase 1 login exists)

| Role | Username | Password | Department |
| --- | --- | --- | --- |
| Admin | `admin` | `demo123` | Maintenance |
| Engineer | `engineer` | `demo123` | Maintenance |
| Reviewer | `reviewer` | `demo123` | Maintenance |

These are fake users. Passwords are hashed into SQLite on first run. Login uses Streamlit session state only — **no JWT**.

On the Dashboard, Maintenance users can click **Prepare demo files** once to index the synthetic PDFs.

---

## 9. Daily cheat sheet

```bash
# 1. go to project
cd /home/rgukt-basar/sih

# 2. turn on Python environment
source .venv/bin/activate

# 3. (only if packages changed)
pip install -r requirements.txt

# 4. start the website
streamlit run app.py
```

---

## 10. Common errors

| What you see | What it means | Fix |
| --- | --- | --- |
| `streamlit: command not found` | venv off, or packages not installed | `source .venv/bin/activate` then `pip install -r requirements.txt` |
| `No such file: app.py` | Wrong folder | `cd /home/rgukt-basar/sih` |
| Browser says connection refused | App is not running | Run `streamlit run app.py` and wait for the Local URL |
| Port 8501 already in use | Old Streamlit still running | In that terminal press `Ctrl+C`, or run `streamlit run app.py --server.port 8502` |
| `LLM_API_KEY` / 401 unauthorized | Bad or empty API key | Recreate the key and paste into `.env` with no spaces |
| First PDF search is slow | Embedding model downloading | Wait; needs internet once |
| `ModuleNotFoundError` | Missing package | `pip install -r requirements.txt` |

---

## 11. What you should NOT run

This student prototype is **not** the old Docker / Next.js / Postgres plan.

Do not run:

- `docker compose up`
- `npm install` / `npm run dev`
- PostgreSQL or Qdrant commands
- Ollama (not used in this prototype)

One command starts everything: `streamlit run app.py`.

---

## 12. Files you will touch vs files the builder writes

| You (operator) | Builder (coding agent) |
| --- | --- |
| `.env` (secrets) | `app.py`, `auth.py`, `database.py`, … |
| Terminal commands above | UI pages, RAG, LLM calls |
| Demo PDFs/CSV later under `demo/` | Extraction, charts, reports |

Never commit `.env`. `.gitignore` already blocks it.
