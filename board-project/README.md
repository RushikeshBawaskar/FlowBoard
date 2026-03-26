# Task Flow

Task Flow is a full-stack project management app with FastAPI + PostgreSQL backend and React frontend.
It supports JWT auth, board CRUD, card create/edit/move, soft-delete behavior, and optimistic drag-and-drop UX.

## Implemented features

- JWT authentication (`register`, `login`)
- Board CRUD:
  - create
  - list
  - get board detail (lists + cards)
  - rename
  - soft delete
- Card actions:
  - create
  - edit
  - move across/same list
- Efficient card ordering using fractional indexing (`position_rank`) with rebalance
- Concurrency-safe move endpoint (row locks + transactional logic)
- Soft-delete cascade on board delete (`boards`, `lists`, `cards` set `deleted_at`)
- N+1-safe board detail load via eager loading strategy
- React single-board view with `dnd-kit` + optimistic UI + rollback on API error
- One-command Docker Compose stack for DB + backend + frontend

## Core algorithm and race-condition handling

### Ordering algorithm

This implementation uses fractional indexing (decimal ranks):
- middle insert: `(prev_rank + next_rank) / 2`
- top insert: `next_rank - BASE_GAP`
- bottom insert: `prev_rank + BASE_GAP`
- empty list insert: `BASE_GAP`

If gap between neighbors is below threshold (`<= MIN_GAP`), list rebalance runs and reassigns ranks as:
- `BASE_GAP * 1`, `BASE_GAP * 2`, `BASE_GAP * 3`, ...

### Concurrency strategy for move endpoint

`PATCH /cards/{id}/move`:
- locks moving card (`FOR UPDATE`)
- locks source/target lists in stable order (`FOR UPDATE`)
- locks neighbor cards when provided (`FOR UPDATE`)
- validates neighbor consistency
- computes rank and commits atomically

This prevents corrupted order when concurrent users move cards.

## API summary

Base path: `/api/v1`

Auth:
- `POST /auth/register`
- `POST /auth/login`

Health:
- `GET /health`

Boards:
- `GET /boards`
- `GET /boards/{board_id}`
- `POST /boards`
- `PATCH /boards/{board_id}`
- `DELETE /boards/{board_id}` (soft delete)
- `POST /boards/demo-seed`

Cards:
- `POST /cards`
- `PATCH /cards/{card_id}`
- `PATCH /cards/{card_id}/move`

Note: all board/card endpoints require `Authorization: Bearer <token>`.

## Project structure

- `backend/` FastAPI app (api/services/repos/models/schemas)
- `frontend/` React app (single board view)
- `docker-compose.yml` full local runtime
- `.env.example` environment template
- `TASK_FLOW_IMPLEMENTATION_PLAN.md` planning and architecture notes

## Run with Docker (recommended)

1. Copy env template:
   - `cp .env.example .env`
2. Start stack:
   - `docker-compose up --build -d`
3. Open:
   - Frontend: `http://127.0.0.1:5173`
   - Backend docs: `http://127.0.0.1:8000/docs`

Stop:
- `docker-compose down`

Remove DB volume:
- `docker-compose down -v`

## Local development

Backend:
1. `docker-compose up -d db`
2. `uv sync --project backend`
3. `uv run --project backend task-flow-api`

Frontend:
1. `npm install --prefix frontend`
2. `npm run --prefix frontend dev -- --host 127.0.0.1 --port 5173`

Optional frontend env (`frontend/.env`):

```env
VITE_API_BASE_URL=http://127.0.0.1:8000/api/v1
```

## Configuration

All runtime values are loaded from root `.env` and validated on startup.

Key variables:
- App: `APP_NAME`, `APP_ENV`, `APP_HOST`, `APP_PORT`, `API_V1_PREFIX`
- CORS: `FRONTEND_ORIGINS`, `FRONTEND_ORIGIN_REGEX`
- DB: `POSTGRES_*`, `DATABASE_URL`, `SQL_ECHO`
- Ordering: `BASE_GAP`, `MIN_GAP`
- Auth: `JWT_SECRET_KEY`, `JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`

## Logs and troubleshooting

View logs:
- `docker-compose logs -f backend`
- `docker-compose logs -f frontend`
- `docker-compose logs -f db`

Common issues:
- CORS: verify frontend origin in `FRONTEND_ORIGINS`
- 401 errors: token missing/expired, login again
- DB port conflict on `5432`: stop local DB service or change `POSTGRES_PORT`

## About `frontend_tmp`

`frontend_tmp` was a temporary scaffold folder from initial setup and is removed from the final project.
