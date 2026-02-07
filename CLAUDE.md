# CLAUDE.md

## Project Overview

**FotoRestorer** (ФотоРеставратор) — a full-stack web app for AI-powered restoration and colorization of old photographs. Users upload damaged/B&W photos, which get processed through AI pipelines (CodeFormer for face restoration, DeOldify for colorization). Freemium model: 3 free photos, then paid packs or monthly subscriptions via YooKassa (СБП, МИР, российские карты). Supports single photo, batch upload (up to 20), two-photo glare removal, and direct camera capture on mobile.

All UI text is in Russian.

## Tech Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| Frontend | React + Vite | React 18.2, Vite 5.0 |
| Backend | Python FastAPI | FastAPI 0.104, Python 3.12 |
| AI Models | Replicate API | CodeFormer, DeOldify |
| Payments | YooKassa | yookassa 3.2 |
| Image Processing | OpenCV + Pillow | opencv-headless 4.9, Pillow 10.1 |
| Containerization | Docker | Multi-stage build, Node 20 + Python 3.12 |

## Project Structure

```
├── backend/
│   ├── main.py            # FastAPI app, all API route handlers
│   ├── restore.py         # AI restoration pipeline (Replicate calls)
│   ├── preprocess.py      # Image preprocessing (crop, scratch removal, glare merge)
│   ├── payments.py        # YooKassa checkout, subscriptions + webhook handling
│   ├── storage.py         # JSON-file session/usage/subscription tracking
│   ├── config.py          # Settings from environment variables
│   ├── data/              # Runtime data (usage.json) — gitignored
│   └── requirements.txt   # Python dependencies (pinned versions)
├── frontend/
│   ├── src/
│   │   ├── App.jsx        # Single main React component (all UI logic)
│   │   ├── main.jsx       # React entry point
│   │   └── styles.css     # All application styles
│   ├── index.html         # HTML template
│   ├── vite.config.js     # Vite config with API proxy
│   └── package.json       # Frontend dependencies
├── uploads/               # Runtime directory for originals + results — gitignored
├── Dockerfile             # Multi-stage: Node build → Python runtime
├── docker-compose.yml     # Single service with volumes for uploads + data
├── .env.example           # Required environment variables template
└── README.md              # User-facing documentation
```

## Development Setup

### Prerequisites
- Python 3.12+
- Node.js 20+
- Replicate API token (for AI model access)

### Manual Setup
```bash
# Backend
cd backend
pip install -r requirements.txt

# Frontend
cd frontend
npm install
```

### Running Locally
```bash
# Terminal 1 — Backend (from project root)
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2 — Frontend (from project root)
cd frontend
npm run dev    # Starts Vite dev server on port 5173
```

The Vite dev server proxies `/api` requests to `localhost:8000`.

### Docker
```bash
cp .env.example .env   # Fill in real values
docker compose up --build
```

Runs on port 8000 (serves both API and built frontend).

## Environment Variables

All required in `.env` (see `.env.example`):

| Variable | Purpose |
|----------|---------|
| `REPLICATE_API_TOKEN` | Replicate API key for AI model calls |
| `YOOKASSA_SHOP_ID` | YooKassa shop ID (из личного кабинета) |
| `YOOKASSA_SECRET_KEY` | YooKassa secret key |
| `FREE_PHOTOS_LIMIT` | Free photos per session (default: 3) |
| `UPLOAD_DIR` | Upload directory path (default: `./uploads`) |
| `MAX_FILE_SIZE_MB` | Max upload size in MB (default: 20) |

## API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/status` | Session info + remaining photo count + subscription status |
| `POST` | `/api/restore` | Upload & restore single photo |
| `POST` | `/api/restore-multi` | Upload 2 photos for glare removal + restore |
| `POST` | `/api/restore-batch` | Upload & restore multiple photos at once (up to 20) |
| `GET` | `/api/download/{photo_id}` | Download restored result |
| `GET` | `/api/packs` | List available paid photo packs |
| `GET` | `/api/subscriptions` | List available subscription plans |
| `POST` | `/api/checkout` | Create YooKassa payment (one-time pack) |
| `POST` | `/api/subscribe` | Create YooKassa payment (subscription with autopayment) |
| `POST` | `/api/webhook/yookassa` | YooKassa payment webhook (packs + subscriptions) |

Session tracking uses cookies (`session_id`), not authentication.

## Key Architecture Decisions

- **Single-component frontend**: All UI lives in `App.jsx` with React hooks for state management. No routing library or state management library.
- **JSON file storage**: Session usage tracked in `backend/data/usage.json` — no database.
- **Optional OpenCV**: `preprocess.py` degrades gracefully if OpenCV is unavailable (try-except imports).
- **Replicate API**: AI models run remotely via Replicate, not locally. Requires network access and valid API token.
- **Static file serving**: In production, FastAPI serves the built frontend from `frontend/dist/`.

## Processing Pipelines

**Single photo**: upload → validate → auto-crop → remove scratches → enhance → CodeFormer (face restore) → DeOldify (colorize) → save result

**Batch upload**: upload multiple files → each file goes through the single photo pipeline independently → return results array

**Two-photo glare removal**: upload 2 angles → ORB feature alignment → glare detection (brightness > 220) → composite with Gaussian seam blending → then same pipeline as single photo

**Camera capture**: Uses HTML5 `<input capture="environment">` to open the rear camera directly on mobile devices, then sends the captured photo through the single photo pipeline

## Code Conventions

- **Python**: snake_case functions/variables, PascalCase classes, module-level docstrings, async endpoints
- **JavaScript**: camelCase functions/variables, PascalCase components, React hooks patterns
- **Section separators**: Both Python and JS use `# ──` / `// ──` comment dividers for code sections
- **Error messages**: All user-facing errors are in Russian
- **Imports**: Python backend uses relative imports (no package prefix) when running from `backend/` directory

## Testing & Linting

No automated testing or linting is currently configured. There are no test files, pytest config, ESLint config, or Prettier config in the repository.

## Common Tasks

**Add a new API endpoint**: Define the route handler in `backend/main.py`, following the existing pattern with session cookie handling and `JSONResponse`.

**Add a new preprocessing step**: Add the function in `backend/preprocess.py`, then call it from the pipeline in `backend/restore.py`.

**Modify the UI**: All frontend logic is in `frontend/src/App.jsx`, styles in `frontend/src/styles.css`.

**Change payment packs**: Edit the `PHOTO_PACKS` constant in `backend/payments.py`.

**Change subscription plans**: Edit the `SUBSCRIPTION_PLANS` constant in `backend/payments.py`. Prices are defined directly in the code (no separate price IDs needed — YooKassa creates payments with amounts, not price references).
