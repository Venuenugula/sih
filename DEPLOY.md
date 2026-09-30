# Deploy INDUSAI

Student SIH prototype: one Streamlit process, SQLite, ChromaDB on disk. No Docker required.

Choose one path below.

---

## Before you deploy

1. **Secrets:** Never commit `.env` or real API keys. Use `.env` on a VPS or Streamlit **Secrets** in the cloud.
2. **Demo files:** Commit `demo/` (PDFs, `inspection.jpg`, `sensor_data.csv`) so judges can run the PUMP-204 flow.
3. **First run:** Login, Dashboard → **Prepare demo files**, then Investigation.

---

## Option A — Same machine, share on your network (fastest)

Good for lab Wi‑Fi or a single VM.

```bash
cd /path/to/sih
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env → LLM_API_KEY=...

chmod +x scripts/run_server.sh
./scripts/run_server.sh
```

Open from another device: `http://<server-ip>:8501`

Firewall (if enabled):

```bash
sudo ufw allow 8501/tcp
```

---

## Option B — VPS / college server (systemd)

1. Clone or copy the `sih` folder to the server.
2. Create venv, install deps, add `.env` (same as local).
3. Edit `deploy/indusai.service` — set `User`, `WorkingDirectory`, and paths.
4. Install and start:

```bash
sudo cp deploy/indusai.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now indusai
sudo systemctl status indusai
```

Optional: put **nginx** in front with HTTPS and proxy to `127.0.0.1:8501`.

**Note:** SQLite and ChromaDB live on that server’s disk. Back up `data/` and `chroma_db/` if you care about audit logs and indexed PDFs.

---

## Option C — Streamlit Community Cloud (public URL)

Best for a hackathon demo link without managing a server.

1. Push this project to **GitHub** (repo root should contain `app.py`, or set **Main file path** to `sih/app.py` if the repo is monorepo).
2. Go to [share.streamlit.io](https://share.streamlit.io) → **New app** → select repo and branch.
3. **Main file path:** `app.py` (or `sih/app.py`).
4. **App settings → Secrets** — paste TOML from `.streamlit/secrets.toml.example` and set `LLM_API_KEY`.
5. Deploy.

`config.py` reads Streamlit secrets into the same variables as `.env`.

**Limits:** Free tier has memory/CPU caps. First load may be slow (SentenceTransformers + Chroma). Ephemeral disk: re-run **Prepare demo files** after cold starts if Chroma is empty.

---

## Environment variables

| Variable | Required for full demo |
|----------|-------------------------|
| `LLM_API_KEY` | Yes (AI answer + image analysis) |
| `LLM_API_BASE_URL` | Yes (Gemini OpenAI-compatible URL) |
| `LLM_MODEL` / `VISION_MODEL` | Yes |
| Demo user passwords | Optional (defaults in `.env.example`) |

Everything else has sane defaults in `config.py`.

---

## Health check after deploy

```bash
cd /path/to/sih
source .venv/bin/activate
python golden_path_test.py
```

Or manually: login `engineer` / `demo123` → Investigation → **Use demo image** → **ANALYZE MACHINE**.

---

## What not to do for this prototype

- Do not commit `.env` or `.streamlit/secrets.toml`.
- Do not expose demo passwords on a public URL without understanding they are **demo-only**.
- Replacing SQLite/Streamlit with Postgres/React is out of scope for this repo.
