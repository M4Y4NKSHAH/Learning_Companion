# 🚀 Setup & Run Guide — Learning Companion

> How to go from a fresh clone to a running tutor. Two processes:
> **backend** (FastAPI, port 8000) + **frontend** (Vite, port 5173).

---

## 1. Prerequisites

- **Python 3.11+** (a `venv/` already exists in the repo — Python 3.13)
- **Node.js + npm** (required for the Vite frontend)
- A **Google AI (Gemini) API key** — optional but strongly recommended. Without it the
  app still runs using hardcoded fallback responses.

Check versions:

```powershell
python --version
node --version
npm --version
```

---

## 2. Environment Variables (`.env`)

The app reads `GEMINI_API_KEY` (falls back to `GOOGLE_API_KEY`). Create a `.env` file at
the **project root** (easiest when running `python backend/app.py` from root) or inside
`backend/`:

```
GEMINI_API_KEY=your_actual_api_key_here
```

`.env` is already git-ignored — do not commit real keys.

---

## 3. Install Backend Dependencies

Activate the virtual environment and install the requirements from `requirements.txt`:

```powershell
.\venv\Scripts\activate
pip install -r requirements.txt
```

---

## 4. Start the Backend

### Option A — from the project root (recommended)

```powershell
.\venv\Scripts\activate
python backend/app.py
```

### Option B — from inside `backend/`

```powershell
cd backend
..\venv\Scripts\activate
python app.py
```

The backend serves on **`http://127.0.0.1:8000`**. Verify:

- Swagger UI: `http://127.0.0.1:8000/docs`
- Health-ish manual call: `Invoke-RestMethod http://127.0.0.1:8000/docs` (or just open
  the Swagger page).

> ⚠️ The backend uses flat imports (`from fuzzy_engine import …`). Both documented launch
> paths work because Python adds the script's own folder to `sys.path` (e.g. `backend/`
> when running `python backend/app.py`). Don't move `app.py` into a package without
> converting these imports.

---

## 5. Start the Frontend

In a **second terminal**:

```powershell
cd frontend
npm install        # first time only (or after package.json changes)
npm run dev        # the first run may need: npm run dev -- --force
```

Vite prints the local URL — usually **`http://localhost:5173`** (host is `true`, so it's
also reachable from LAN IP). Open it in a browser and use "Launch Dashboard".

---

## 6. (Optional) Build the RAG Knowledge Base

The ChromaDB collection `curriculum_repository` is only rebuilt **when you add new
textbooks**. It is not needed on every startup — the vector DB persists on disk.

When you add a new OpenStax textbook:

1. Save the extracted text as a `.txt` file in `backend/data/curriculum/`.
2. Add an entry to the `textbooks` list at the **bottom of `backend/database_ingest.py`**
   (subject + academic tier).
3. With the venv active, run the ingestion pipeline — it deletes the old collection and
   re-embeds everything:

```powershell
python backend/database_ingest.py
```

This prints per-batch progress and a 3-row preview of
`backend/data/ednet/ednet_small_sample.csv`.

---

## 7. Ports Summary

| Process | URL | Command |
| --- | --- | --- |
| Backend (FastAPI) | `http://127.0.0.1:8000` | `python backend/app.py` |
| Backend docs | `http://127.0.0.1:8000/docs` | — |
| Frontend (Vite) | `http://localhost:5173` | `npm run dev` (from `frontend/`) |

The frontend calls the backend at the hardcoded base `http://127.0.0.1:8000` — keep the
backend on port 8000.

---

## 8. Troubleshooting Cheat-Sheet

| Problem | Fix |
| --- | --- |
| `ModuleNotFoundError: fuzzy_engine` | Start from repo root (`python backend/app.py`) or from `backend/` |
| Chat returns generic text only | Add `GEMINI_API_KEY` to `.env`, restart backend |
| Chroma collection empty / 1 fallback chunk | Run `python backend/database_ingest.py` |
| `npm install` errors | Delete `frontend/node_modules` + `package-lock.json`, reinstall |
| Frontend can't reach backend | Keep backend on 8000; check CORS is `"*"` locally |
| Port conflicts | Change TRUSTED dev ports; frontend strictly needs 8000 reachable |

---

## 9. Useful Maintenance Commands

```powershell
# Python dependency freeze
.\venv\Scripts\activate
pip freeze > requirements-lock.txt

# Build the frontend production bundle
cd frontend
npm run build          # outputs to frontend/dist/

# Check which branches exist
git branch -a
```