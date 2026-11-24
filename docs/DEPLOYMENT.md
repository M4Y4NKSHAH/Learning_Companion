# 🚀 Deployment Guide: LearnerHelp on Render & Vercel

This guide explains how to deploy **LearnerHelp** publicly with the backend hosted on **Render** and the frontend hosted on **Vercel**.

---

## 1. Architecture Overview

- **Frontend (Vercel):** React + Vite Single Page Application (SPA), styled with Tailwind Japandi theme. Hosted globally via edge CDN with rewrite rules in `vercel.json`.
- **Backend (Render):** FastAPI application with LangGraph state machine, ChromaDB vector database, and BM25 hybrid search engine. Exposed with health check at `/health` and dynamic `$PORT` binding.
- **Persistence:** Render Persistent Disk mounted at `/data` (`DATA_DIR=/data`) to preserve custom courses (`/data/courses`), learning analytics SQLite database (`/data/analytics.db`), and Chroma vector collections (`/data/chroma_knowledge_base`).

---

## 2. Deploying Backend to Render

### Method A: Using Render Blueprint (`render.yaml`)

1. Connect your Git repository to **Render** (https://dashboard.render.com).
2. Click **New +** -> **Blueprint**.
3. Select this repository. Render will automatically detect `render.yaml` and configure:
   - Service name: `learnerhelp-backend`
   - Runtime: Python (or Docker via `Dockerfile`)
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `uvicorn backend.app:app --host 0.0.0.0 --port $PORT`
   - Health Check Path: `/health`
   - Persistent Disk: `learnerhelp-disk` mounted at `/data` (1 GB on Starter plan)
   > **Note on Render Free Tier vs Starter Plan:** Render only supports persistent disks on `starter` or higher plans ($7/mo + $0.25/mo disk). If you prefer the 100% free tier on Render, edit `render.yaml` to change `plan: starter` to `plan: free` and delete the `disk:` block. In free mode, custom courses and sqlite analytics will store locally in container memory.
4. In the Render Environment Variables tab, fill in your:
   - `GEMINI_API_KEY`: Your Google Gemini API key
   - `CORS_ORIGINS`: `*` (or your Vercel URL, e.g. `https://learnerhelp.vercel.app`)
5. Click **Apply**.
6. Once deployed, copy your Render service URL (e.g. `https://learnerhelp-backend.onrender.com`). Verify by visiting `https://learnerhelp-backend.onrender.com/health`.

---

## 3. Deploying Frontend to Vercel

1. Log into **Vercel** (https://vercel.com).
2. Click **Add New...** -> **Project**.
3. Import your Git repository.
4. Configure project settings:
   - **Framework Preset:** Vite
   - **Root Directory:** `frontend` (or leave as root if using the root `vercel.json`)
   - **Build Command:** `npm run build`
   - **Output Directory:** `dist`
5. In **Environment Variables**, add:
   - `VITE_API_BASE`: `https://learnerhelp-backend.onrender.com` (your Render backend URL)
6. Click **Deploy**.
7. Vercel will build and deploy your application. Access your live app at `https://your-project.vercel.app`.

---

## 4. Verification Checklist

- [x] Backend responds to `GET /health` with `{"status": "healthy", "service": "LearnerHelp API"}`.
- [x] Backend responds to `GET /` with welcome status.
- [x] Frontend can fetch courses from `${VITE_API_BASE}/api/material/courses`.
- [x] Custom course ingestion creates chapter-isolated embeddings in ChromaDB.
- [x] Chapter-scoped queries prevent cross-chapter leakage.
- [x] Spaced Repetition (SM-2) reviews and learning analytics persist across server restarts.
