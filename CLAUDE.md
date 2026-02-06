# CLAUDE.md

## Project Overview

**FotoRestorer** (ФотоРеставратор) — a web application for restoring and colorizing old photographs using AI. Built with a Python/FastAPI backend and a React/Vite frontend. The UI is in Russian.

Key capabilities: scratch/noise removal, face restoration (CodeFormer via Replicate API), B&W-to-color conversion (DeOldify via Replicate API), lens glare removal from two-angle photos, and auto-crop/perspective correction.

Freemium model: 3 free photos per session, then paid packs via Stripe.

## Repository Structure

```
.
├── backend/                 # Python FastAPI backend
│   ├── main.py             # API routes and FastAPI app
│   ├── restore.py          # Photo restoration pipeline (Replicate API calls)
│   ├── preprocess.py       # Image preprocessing (OpenCV: crop, denoise, scratch removal)
│   ├── payments.py         # Stripe integration
│   ├── storage.py          # JSON-based session/usage storage
│   ├── config.py           # Pydantic settings from environment
│   └── requirements.txt    # Pinned Python dependencies
├── frontend/                # React + Vite frontend
│   ├── package.json        # NPM config and scripts
│   ├── vite.config.js      # Vite config with API proxy
│   ├── index.html          # HTML entry point
│   └── src/
│       ├── main.jsx        # React entry point
│       ├── App.jsx         # Main application component (all sub-components inline)
│       └── styles.css      # All application styles
├── Dockerfile              # Multi-stage: Node build → Python runtime
├── docker-compose.yml      # Single-service orchestration
├── .env.example            # Required environment variables template
└── README.md               # Project documentation (Russian)
```

## Tech Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| Backend framework | FastAPI | 0.104.1 |
| ASGI server | Uvicorn | 0.24.0 |
| Image processing | OpenCV (headless), Pillow, NumPy | 4.9.0, 10.1.0, 1.26.3 |
| AI inference | Replicate API | 0.22.0 |
| Payments | Stripe | 7.8.0 |
| Frontend framework | React | 18.2.x |
| Build tool | Vite | 5.0.8 |
| Container | Docker (multi-stage), Docker Compose | Node 20 + Python 3.12 |

## Development Setup

### Prerequisites

- Python 3.12+
- Node.js 20+
- A `.env` file (copy from `.env.example`) with at minimum `REPLICATE_API_TOKEN`

### Running Locally

**Backend:**
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

**Frontend (separate terminal):**
```bash
cd frontend
npm install
npm run dev
```

The Vite dev server runs on port 5173 and proxies `/api/*` requests to `localhost:8000`.

### Running with Docker

```bash
cp .env.example .env
# Fill in API keys in .env
docker compose up --build
```

Application serves on port 8000 (both API and static frontend).

## Common Commands

| Task | Command | Directory |
|------|---------|-----------|
| Start backend (dev) | `uvicorn main:app --reload --port 8000` | `backend/` |
| Start frontend (dev) | `npm run dev` | `frontend/` |
| Build frontend | `npm run build` | `frontend/` |
| Preview frontend build | `npm run preview` | `frontend/` |
| Docker build & run | `docker compose up --build` | root |
| Install Python deps | `pip install -r requirements.txt` | `backend/` |
| Install JS deps | `npm install` | `frontend/` |

## API Endpoints

All routes are prefixed with `/api/`:

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/status` | Session usage stats (remaining photos, used count) |
| POST | `/api/restore` | Upload and restore a single photo |
| POST | `/api/restore-multi` | Upload 2 photos for glare removal + restoration |
| GET | `/api/download/{photo_id}` | Download a restored photo |
| GET | `/api/packs` | List available payment packages |
| POST | `/api/checkout` | Create a Stripe checkout session |
| POST | `/api/webhook/stripe` | Handle Stripe payment webhooks |

## Processing Pipeline

**Single photo:** auto-crop/perspective correction → scratch removal (inpainting) → contrast enhancement (CLAHE) + denoising → CodeFormer face restoration → DeOldify colorization

**Two-angle photos:** image alignment (ORB features + homography) → glare detection & compositing → seam smoothing (Gaussian feathering) → standard single-photo pipeline

## Architecture Notes

- **No test suite** — no pytest, Jest, or other test frameworks are configured.
- **No linter/formatter** — no ESLint, Prettier, Black, or similar tools are set up.
- **No CI/CD** — no GitHub Actions or other pipeline configurations exist.
- **Session tracking** uses cookies (`session_id`) and a JSON file at `backend/data/usage.json`.
- **File uploads** are stored in `uploads/originals/` and `uploads/results/`.
- In production (Docker), the backend serves the built frontend as static files from `frontend/dist/`.

## Code Conventions

- **Python**: snake_case for files and functions. Modules are organized by concern (`restore`, `preprocess`, `payments`, `storage`, `config`).
- **JavaScript/JSX**: PascalCase for React components. All components live in a single `App.jsx` file. ES modules (`"type": "module"` in package.json).
- **CSS**: kebab-case class names (e.g., `.upload-area`, `.status-bar`, `.mode-btn`). Single stylesheet at `frontend/src/styles.css`.
- **Error messages** in API responses are in Russian.
- **Environment configuration** is managed via `.env` file and Pydantic settings in `backend/config.py`.

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `REPLICATE_API_TOKEN` | Yes | — | Replicate API key for AI models |
| `STRIPE_SECRET_KEY` | No | — | Stripe secret key for payments |
| `STRIPE_PRICE_ID` | No | — | Stripe price ID for photo packs |
| `STRIPE_WEBHOOK_SECRET` | No | — | Stripe webhook signing secret |
| `FREE_PHOTOS_LIMIT` | No | 3 | Free photos per session |
| `UPLOAD_DIR` | No | `./uploads` | Upload storage directory |
| `MAX_FILE_SIZE_MB` | No | 20 | Maximum upload file size in MB |

## External Services

- **Replicate** (replicate.com) — runs CodeFormer and DeOldify AI models for photo restoration and colorization.
- **Stripe** (stripe.com) — handles payment processing for photo pack purchases.
