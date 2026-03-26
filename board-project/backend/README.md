# Task Flow Backend

FastAPI backend for Task Flow.

## Stack

- Python 3.10+
- FastAPI
- SQLAlchemy async + asyncpg
- PostgreSQL
- Pydantic v2
- `uv` package manager

## Architecture

Layered modules:
- `app/api/` HTTP routes
- `app/services/` business logic
- `app/repos/` data access
- `app/models/` ORM entities
- `app/schemas/` API contracts
- `app/core/` config + security + logging
- `app/db/` session + schema bootstrap

## Auth

Implemented JWT auth endpoints:
- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`

Board and card endpoints require bearer token.

## Implemented endpoints

Health:
- `GET /api/v1/health`

Boards:
- `GET /api/v1/boards`
- `GET /api/v1/boards/{board_id}`
- `POST /api/v1/boards`
- `PATCH /api/v1/boards/{board_id}`
- `DELETE /api/v1/boards/{board_id}` (soft delete)
- `POST /api/v1/boards/demo-seed`

Cards:
- `POST /api/v1/cards`
- `PATCH /api/v1/cards/{card_id}`
- `PATCH /api/v1/cards/{card_id}/move`

## Ordering and concurrency

- Uses fractional indexing via `position_rank` (`NUMERIC(38,19)`).
- Rebalance triggers when neighbor gap <= `MIN_GAP`.
- Move endpoint uses row-level locks and transaction boundaries to handle concurrent moves safely.

## Soft delete behavior

- Entities include `deleted_at`.
- Board delete sets `deleted_at` for board, lists, and cards.
- Soft-deleted board fetch returns 404 in active APIs.

## N+1 prevention

`GET /boards/{id}` uses eager loading (`selectinload` + loader criteria) to return board + lists + cards without query explosion.

## Local run

From repo root:

1. Start DB:
   - `docker-compose up -d db`
2. Install deps:
   - `uv sync --project backend`
3. Run API:
   - `uv run --project backend task-flow-api`

Swagger:
- `http://127.0.0.1:8000/docs`

## Docker logs

- `docker-compose logs -f backend`

## Move card E2E tests

The move test suite covers:
- Same-list moves: top, middle, bottom.
- Cross-list moves: top, middle, bottom.
- Moves into and out of empty lists.
- Repeated move consistency checks (no duplicate/lost cards).
- Mixed multi-step move sequence across lists.

Run from repo root:
- `uv run --project backend pytest backend/app/tests/test_card_move_api_e2e.py -q`

If you are routing through frontend in Docker (Nginx proxy), use:
- `TASKFLOW_API_BASE_URL=http://127.0.0.1:5173/api/v1 uv run --project backend pytest backend/app/tests/test_card_move_api_e2e.py -q`

## Configuration

All settings are read from root `.env` and validated on startup.

Important variables:
- `DATABASE_URL`
- `SQL_ECHO`
- `BASE_GAP`
- `MIN_GAP`
- `JWT_SECRET_KEY`
- `JWT_ALGORITHM`
- `ACCESS_TOKEN_EXPIRE_MINUTES`
- `FRONTEND_ORIGINS`
- `FRONTEND_ORIGIN_REGEX`
