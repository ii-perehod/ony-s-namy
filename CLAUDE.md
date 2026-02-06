# CLAUDE.md — AI Assistant Guide for FotoRestorer

## Project Overview

**FotoRestorer** is a full-stack web application for AI-powered old photo restoration and colorization. Users upload damaged, faded, or black-and-white photos and receive restored, colorized results. The app supports single-photo mode and a two-photo glare-removal mode.

- **Frontend:** React 18 + Vite (JavaScript, no TypeScript)
- **Backend:** Python 3.12 + FastAPI
- **AI Models:** CodeFormer (face/damage restoration) and DeOldify (colorization) via Replicate API
- **Payments:** Stripe (3 free photos, then paid packs)
- **Language:** UI text is in Russian

## Repository Structure

```
.
├── frontend/                  # React SPA (Vite)
│   ├── src/
│   │   ├── App.jsx           # Main app component (all UI logic)
│   │   ├── main.jsx          # React entry point
│   │   └── styles.css        # All styles (dark theme)
│   ├── index.html            # HTML shell
│   ├── package.json          # Node dependencies & scripts
│   └── vite.config.js        # Vite config with API proxy
├── backend/                   # FastAPI Python API
│   ├── main.py               # API routes & middleware
│   ├── restore.py            # AI pipeline (CodeFormer + DeOldify)
│   ├── preprocess.py         # Image preprocessing (crop, scratch removal, enhancement)
│   ├── payments.py           # Stripe checkout & webhooks
│   ├── storage.py            # JSON-based usage tracking
│   ├── config.py             # Environment variable settings
│   └── requirements.txt      # Python dependencies
├── Dockerfile                 # Multi-stage build (Node → Python)
├── docker-compose.yml         # Single-service compose config
├── .env.example               # Required environment variables template
├── .gitignore
└── README.md                  # Project docs (Russian)
```

## Development Setup

### Prerequisites

- Node.js 20+
- Python 3.12+
- A Replicate API token (required for AI processing)
- Stripe keys (required for payments; test keys work for dev)

### Environment Variables

Copy `.env.example` to `.env` and fill in:

```
REPLICATE_API_TOKEN=r8_...        # From replicate.com
STRIPE_SECRET_KEY=sk_test_...     # From Stripe dashboard
STRIPE_PRICE_ID=price_...         # Stripe product price
STRIPE_WEBHOOK_SECRET=whsec_...   # Stripe webhook signing secret
FREE_PHOTOS_LIMIT=3               # Free photos per session
UPLOAD_DIR=./uploads              # Where uploaded/processed images go
MAX_FILE_SIZE_MB=20               # Max upload size
```

### Running Locally

**Frontend** (terminal 1):
```bash
cd frontend
npm install
npm run dev          # Starts at http://localhost:5173
```

**Backend** (terminal 2):
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Vite proxies `/api` requests to `localhost:8000` during development.

### Running with Docker

```bash
cp .env.example .env   # Edit with real credentials
docker compose up --build
# App available at http://localhost:8000
```

## Build Commands

### Frontend (from `frontend/` directory)

| Command           | Description                        |
|-------------------|------------------------------------|
| `npm run dev`     | Start Vite dev server (port 5173)  |
| `npm run build`   | Production build to `dist/`        |
| `npm run preview` | Preview production build locally   |

### Backend

| Command                                      | Description                     |
|----------------------------------------------|---------------------------------|
| `uvicorn main:app --reload --port 8000`      | Dev server with auto-reload     |
| `uvicorn backend.main:app --host 0.0.0.0 --port 8000` | Production (from project root) |

## Testing & Linting

**No test framework or linting is currently configured.** There are no test files, no pytest/jest setup, no ESLint/Prettier/Black/Pylint configuration, and no CI/CD pipeline.

When adding tests:
- Frontend: consider Vitest (already Vite-based)
- Backend: consider pytest with httpx for FastAPI async testing

## API Endpoints

All endpoints are prefixed with `/api`:

| Method | Endpoint               | Purpose                              |
|--------|------------------------|--------------------------------------|
| GET    | `/api/status`          | Session info (remaining photos, etc) |
| POST   | `/api/restore`         | Upload single photo for restoration  |
| POST   | `/api/restore-multi`   | Upload 2 photos for glare removal    |
| GET    | `/api/download/{id}`   | Download processed result            |
| GET    | `/api/packs`           | List available photo packs           |
| POST   | `/api/checkout`        | Create Stripe checkout session       |
| POST   | `/api/webhook/stripe`  | Stripe payment webhook               |

Error responses use HTTP status codes: 400 (validation), 402 (quota exhausted), 404 (not found), 500 (processing error). Error messages are in Russian.

## Architecture & Key Patterns

### Frontend

- **Single-file component architecture:** All UI lives in `App.jsx` with inline sub-components (`Tips`, `ProcessingSteps`, `ImageComparison`, `PaymentSection`).
- **State management:** React hooks only (`useState`, `useEffect`, `useRef`, `useCallback`). No global state library.
- **File uploads:** FormData with `fetch()` to `/api/restore` or `/api/restore-multi`.
- **Session tracking:** HTTP-only `session_id` cookie set by the backend.
- **Styling:** Single `styles.css` file, dark theme, mobile-responsive. No CSS framework.

### Backend

- **Layered modules:** `main.py` (routing) → `restore.py` (AI pipeline) → `preprocess.py` (image processing). Payments and storage are separate modules.
- **AI pipeline:** preprocess (auto-crop, scratch removal, enhancement) → CodeFormer (restore) → DeOldify (colorize). All AI calls go through Replicate API.
- **Session tracking:** UUID-based session IDs stored in cookies. Usage data persisted to `backend/data/usage.json` (no database).
- **OpenCV fallback:** `preprocess.py` checks for OpenCV availability (`HAS_CV2` flag) and falls back to PIL-only processing if unavailable.
- **Config:** Singleton `Settings` class in `config.py` reads from environment variables via `python-dotenv`.

### Data Storage

- **No database.** Usage tracking is a JSON file at `backend/data/usage.json`.
- **Uploaded images:** `uploads/originals/` and `uploads/results/`.
- These directories are Docker volume-mounted for persistence.

## Conventions & Guidelines

- **UI language is Russian.** All user-facing strings (error messages, labels, tips) are in Russian.
- **No TypeScript.** Frontend is vanilla JavaScript with JSX.
- **ESM modules.** Frontend uses `"type": "module"` in package.json.
- **Async endpoints.** All FastAPI routes use `async def`.
- **UUID identifiers.** Photo IDs and session IDs are UUID v4 strings.
- **Image format.** All processed results are saved as JPEG regardless of input format.
- **No authentication.** Users are anonymous; tracked only by session cookie.
- **CORS is wide open** (`allow_origins=["*"]`), suitable for development.

## Common Tasks

### Adding a new API endpoint

1. Add the route in `backend/main.py` following existing patterns (async def, Cookie-based session).
2. Use `_get_session_id()` for session handling.
3. Return `JSONResponse` and set the session cookie on the response.

### Modifying the AI pipeline

1. Edit `backend/restore.py` for pipeline changes.
2. Edit `backend/preprocess.py` for image preprocessing changes.
3. The pipeline is: `preprocess → CodeFormer (Replicate) → DeOldify (Replicate)`.

### Adding frontend UI

1. All UI is in `frontend/src/App.jsx`. Add new sub-components inline or extract to separate files.
2. Styles go in `frontend/src/styles.css`.
3. API calls use `fetch("/api/...")` — the Vite proxy handles routing in dev.

### Docker deployment

1. `docker compose up --build` rebuilds both frontend and backend.
2. The frontend is built in a Node stage and served as static files by FastAPI in production.
3. Persistent data lives in mounted volumes: `./uploads` and `./backend/data`.
