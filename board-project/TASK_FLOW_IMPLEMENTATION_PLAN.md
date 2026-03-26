# Task Flow: Full Stack System Design and Implementation Plan

## 1) Objective and Success Criteria

Build a production-grade Task Flow app with:

1. FastAPI backend (async + PostgreSQL) that is safe under concurrency and avoids N+1 issues.
2. React frontend board view with drag-and-drop and optimistic updates.
3. Phased container strategy: Dockerized PostgreSQL first for development, then containerize the full stack after app completion.

Definition of done:

1. Card reordering is efficient (no bulk integer-shift updates per move).
2. Soft deletes are enforced at API level with logical cascading.
3. `GET /boards/{id}` returns board, lists, cards in one optimized API response.
4. Concurrent card moves are deterministic and protected by transaction strategy.
5. No hardcoded operational values in code; runtime config is sourced from `.env`.

---

## 2) Core Technical Decisions

### 2.1 Ordering Strategy (chosen)

Use **fractional indexing with `NUMERIC` ranks** (not integer positions):

1. `cards.position_rank` is `NUMERIC(38, 19)` and indexed with `(list_id, position_rank)` for active cards.
2. New items at end: `max_rank + 1024`.
3. Move between neighbors: `(prev_rank + next_rank) / 2`.
4. Move to top: `min_rank - 1024`.
5. Move to empty list: default `1024`.
6. If there is no precision gap left, do a **localized list rebalance** (rare) inside the same transaction.

Why:

1. O(1) writes for normal moves (single card update).
2. Easy to reason about and implement in SQLAlchemy/PostgreSQL.
3. Avoids floating-point drift by using `NUMERIC`, not binary float.

### 2.2 Concurrency Strategy (chosen)

Use **transaction + row locking + version check**:

1. `SELECT ... FOR UPDATE` lock on the moving card row.
2. Lock source/target list rows in stable sorted order to avoid deadlocks.
3. Lock neighbor cards (if provided) with `FOR UPDATE`.
4. Optional `expected_version` from client; mismatch returns `409 Conflict`.

Result:

1. Two users moving the same card cannot corrupt order.
2. Last committer does not silently overwrite if version guard is used.

### 2.3 Soft Delete Strategy (chosen)

All entities (`boards`, `lists`, `cards`) include `deleted_at TIMESTAMPTZ NULL`.

1. Soft delete board means timestamping board + all child lists/cards in one transaction.
2. Queries for active data always include `deleted_at IS NULL`.
3. API returns `404` for deleted board resources.

### 2.4 Backend Baseline

1. Python `3.10+`
2. FastAPI + SQLAlchemy `2.x` async engine/session
3. Pydantic `v2` schemas for strict request/response validation
4. `uv` as Python package/dependency manager
5. Alembic migrations
6. PostgreSQL as system of record

### 2.5 Engineering Principles

1. SOLID-first service/repository layering with clear single responsibility.
2. OOP design for domain entities and business services (encapsulation over script-style logic).
3. Dependency inversion: API layer depends on abstractions/services, not concrete DB details.
4. No hardcoded secrets/URLs/tunable constants; configuration comes from `.env` and validated settings models.
5. Centralized constants policy: if a constant exists (for example `BASE_GAP`, `MIN_GAP`), expose it via config rather than inline literals.

---

## 3) Architecture Blueprint

## 3.1 Monorepo Layout

```text
/backend
  /app
    /api
    /core
    /db
    /models
    /schemas
    /services
    /repos
    /tests
/frontend
  /src
    /api
    /components
    /features/board
    /state
    /types
docker-compose.yml
.env.example
README.md
```

## 3.2 Backend Layers

1. API layer: request/response validation, auth dependency, status codes.
2. Service layer: transaction boundaries, ordering and concurrency logic.
3. Repository layer: query composition and data access.
4. Model layer: SQLAlchemy models with relationships and indexes.

---

## 4) Data Model and Constraints

## 4.1 Tables

1. `users`: `id`, `email` (unique), `password_hash`, timestamps.
2. `boards`: `id`, `owner_id`, `name`, timestamps, `deleted_at`.
3. `lists`: `id`, `board_id`, `name`, `position_rank`, timestamps, `deleted_at`.
4. `cards`: `id`, `board_id`, `list_id`, `title`, `description`, `position_rank`, `version`, timestamps, `deleted_at`.

`cards.board_id` is denormalized from list->board for faster validation/filtering and simpler indexes.

## 4.2 Important Indexes

1. `idx_lists_board_active_rank` on `(board_id, position_rank)` where `deleted_at IS NULL`.
2. `idx_cards_list_active_rank` on `(list_id, position_rank)` where `deleted_at IS NULL`.
3. `idx_cards_board_active` on `(board_id)` where `deleted_at IS NULL`.
4. Partial unique index for active board names per owner if needed:
   `UNIQUE(owner_id, lower(name)) WHERE deleted_at IS NULL`.

## 4.3 Integrity Rules

1. Active card must belong to active list and active board.
2. Card move cannot target list from another board.
3. `version` increments on each card update/move.
4. Never hard delete in normal APIs.

---

## 5) Ordering Algorithm Design

## 5.1 Move API Contract

`PATCH /cards/{card_id}/move`

Request:

1. `target_list_id: UUID`
2. `prev_card_id: UUID | null` (card that should be immediately before moved card)
3. `next_card_id: UUID | null` (card that should be immediately after moved card)
4. `expected_version: int | null`

Rules:

1. At least one of `prev_card_id` or `next_card_id` may be null.
2. If both are present, they must be adjacent neighbors in target list at execution time.
3. Neighbor cards cannot be deleted and must belong to target list.

## 5.2 Rank Computation

1. Empty target list:
   `new_rank = 1024`
2. Insert at top (`next_card_id` set, `prev_card_id` null):
   `new_rank = next_rank - 1024`
3. Insert at bottom (`prev_card_id` set, `next_card_id` null):
   `new_rank = prev_rank + 1024`
4. Insert between:
   `new_rank = (prev_rank + next_rank) / 2`

Guard:

1. If `next_rank - prev_rank < MIN_GAP` then rebalance target list and recompute.
2. Suggested `MIN_GAP = 0.000001`.

## 5.3 Rebalance Strategy (rare path)

Within same transaction:

1. Lock all active cards in target list ordered by `position_rank FOR UPDATE`.
2. Reassign ranks as `1024, 2048, 3072, ...`.
3. Recompute moved card rank from refreshed neighbors.

This is O(n) but intentionally rare.

## 5.4 Move Service Pseudocode

```python
async def move_card(card_id, payload, user_id):
    async with session.begin():
        card = lock_active_card_for_update(card_id, user_id)
        validate_expected_version(card, payload.expected_version)

        source_list_id = card.list_id
        target_list_id = payload.target_list_id

        # Lock lists in deterministic order to reduce deadlock risk
        lock_lists_for_update(sorted([source_list_id, target_list_id]))

        prev = lock_neighbor(payload.prev_card_id) if payload.prev_card_id else None
        next = lock_neighbor(payload.next_card_id) if payload.next_card_id else None
        validate_neighbors(prev, next, target_list_id)

        new_rank = compute_rank(prev, next)
        if rank_gap_too_small(prev, next):
            rebalance_list(target_list_id)
            prev, next = refresh_neighbors(...)
            new_rank = compute_rank(prev, next)

        card.list_id = target_list_id
        card.position_rank = new_rank
        card.version += 1

    return card
```

---

## 6) Concurrency and Race Condition Handling

Scenario: two users drag the same card simultaneously.

Handling:

1. First transaction locks card row.
2. Second transaction waits on same row lock.
3. After first commit, second continues with refreshed data.
4. If second request sent stale `expected_version`, return `409 Conflict`.
5. Response includes latest card state so UI can reconcile.

Additional protections:

1. Lock order is deterministic by list id to reduce deadlocks.
2. API returns `422` for invalid/stale neighbor placement.
3. Client retries with fresh board snapshot when conflict occurs.

---

## 7) Soft Delete and Logical Cascade Plan

## 7.1 Delete Board Flow

Inside one transaction:

1. Mark board `deleted_at = now()`.
2. Mark all active lists under board as deleted.
3. Mark all active cards under board as deleted.

## 7.2 Query Behavior

1. `GET /boards/{id}` for deleted board: `404`.
2. `GET /boards/{id}/lists` on deleted board: `404`.
3. Deleted lists/cards are excluded from active board payload.

## 7.3 Developer Safety

1. Create shared query helpers that always enforce `deleted_at IS NULL`.
2. Add integration tests that verify deleted data is not visible through API.

---

## 8) Performance Plan (`GET /boards/{id}`)

Goal: no N+1 explosion.

Use SQLAlchemy loading strategy:

1. Query board once with active filter.
2. `selectinload(Board.lists)` with active filter + order by rank.
3. `selectinload(List.cards)` with active filter + order by rank.
4. `with_loader_criteria` for `deleted_at IS NULL` to avoid accidental deleted-row hydration.

Expected DB round trips: constant small number (typically 3), not per-card.

Response shape:

1. Board fields.
2. List array, each with sorted cards array.

Optional phase 2:

1. Add ETag support for board view caching.
2. Add pagination for extreme card counts (if required later).

---

## 9) Backend API Plan

## 9.1 Auth

1. `POST /auth/register`
2. `POST /auth/login`
3. JWT access token with user id claim.

## 9.2 Boards

1. `POST /boards`
2. `GET /boards`
3. `GET /boards/{id}` (includes lists + cards)
4. `PATCH /boards/{id}`
5. `DELETE /boards/{id}` (soft delete cascade)

## 9.3 Lists

1. `POST /boards/{board_id}/lists`
2. `PATCH /lists/{id}`
3. `DELETE /lists/{id}` (soft delete cards under list)

## 9.4 Cards

1. `POST /lists/{list_id}/cards`
2. `PATCH /cards/{id}` (title/description edits)
3. `PATCH /cards/{id}/move` (transaction-safe rank update)

---

## 10) Frontend Board View Plan

## 10.1 Scope

Single page showing:

1. Board title.
2. Lists as columns.
3. Cards inside each list sorted by rank.

## 10.2 Drag and Drop

Use `dnd-kit`:

1. Detect source and destination list + neighbor card ids on drop.
2. Send move payload with `target_list_id`, `prev_card_id`, `next_card_id`, `expected_version`.

## 10.3 Optimistic UI + Rollback

On drop:

1. Snapshot previous state.
2. Update UI immediately (optimistic reorder).
3. Fire move API request.
4. On success: merge server response (new rank/version).
5. On failure/conflict: rollback snapshot and show toast.

Robustness:

1. Track request ids to ignore stale responses.
2. If `409`, fetch latest board state and re-render.

---

## 11) Docker and Local Environment Plan

### Phase 1 (immediate)

`docker-compose.yml` runs only:

1. `db` (PostgreSQL with persistent volume + healthcheck)

Backend and frontend run directly on host during active development for faster iteration.

### Phase 2 (after core app completion)

Expand Compose to include:

1. `db`
2. `backend` (FastAPI + migrations + uvicorn)
3. `frontend` (Vite build/serve)

All service endpoints and credentials are provided through `.env` variables.

---

## 12) Testing Strategy

## 12.1 Backend Unit Tests

1. Rank computation helper cases (top/bottom/between/empty).
2. Rebalance trigger logic.
3. Soft delete query filters.

## 12.2 Backend Integration Tests

1. Move card across lists and within list.
2. Concurrent move race for same card (`asyncio.gather`) asserts one conflict or deterministic version increments.
3. `GET /boards/{id}` query count stays bounded (no N+1).
4. Deleting board hides lists/cards from API.

## 12.3 Frontend Tests

1. Board rendering from API payload.
2. Drag-drop optimistic reorder.
3. Rollback on failed move request.

## 12.4 E2E Smoke

1. Login.
2. Open board.
3. Move card.
4. Refresh page and verify persisted order.

---

## 13) Edge Cases Checklist

## 13.1 Ordering and Move

1. Move to empty list.
2. Move to top of list.
3. Move to bottom of list.
4. Move between adjacent cards with tiny gap.
5. No-op move (drop card to same place) should return success without update.
6. `prev_card_id` or `next_card_id` references deleted card.
7. Neighbor card belongs to different list/board.
8. Client sends impossible neighbor pair (not adjacent).
9. Card or target list deleted between drag start and drop.
10. Precision gap exhausted after many inserts in same slot.

## 13.2 Concurrency

1. Two users move same card at same time.
2. Two users move different cards into same gap simultaneously.
3. Board deleted while card move in progress.
4. Potential deadlock when cross-list moves happen in opposite directions.

## 13.3 Soft Delete

1. Double-delete same board (idempotent behavior).
2. Soft-deleted board should not appear in board list.
3. Soft-deleted children should never leak via includes/joins.

## 13.4 Frontend

1. Drop outside droppable area.
2. Network timeout after optimistic move.
3. Duplicate in-flight move requests for same card.
4. Out-of-order API responses.

---

## 14) Step-by-Step Execution Plan

1. Initialize monorepo scaffolding and Docker Compose.
2. Add root `.env.example` and wire validated settings objects (no hardcoded operational values).
3. Build backend foundation with `uv`: project setup, config module, DB engine/session, models, Alembic migrations.
4. Implement auth (register/login/JWT guard).
5. Implement board/list/card base APIs with SOLID service/repository separation and soft-delete aware repositories.
6. Implement ordering helpers and move-card transaction service.
7. Add rebalance routine and associated tests.
8. Implement `GET /boards/{id}` with optimized loading and ordering.
9. Add integration tests for soft delete, concurrency, and query count.
10. Build React board view and data fetching.
11. Add drag-and-drop with optimistic update + rollback.
12. Add conflict handling (`409`) and state resync path.
13. Containerize backend/frontend and finalize full Compose setup after core features are complete.
14. Finalize README architecture note with algorithm and race-condition explanation.

---

## 15) README Architecture Note (what to include)

1. Why fractional indexing with `NUMERIC` was selected over integer positions.
2. How transactions + `FOR UPDATE` + optional version checks prevent race corruption.
3. Why `selectinload` strategy avoids N+1 for board payload.
4. How soft-delete cascade is enforced while preserving auditability.

---

## 16) Risks and Mitigations

1. Risk: frequent rebalances in hot lists.
   Mitigation: large initial gap (`1024`), high-precision numeric, measure frequency.
2. Risk: deadlocks under heavy concurrent moves.
   Mitigation: deterministic lock ordering and short transactions.
3. Risk: frontend state drift with optimistic updates.
   Mitigation: rollback snapshot + conflict refetch.
4. Risk: soft-deleted rows leak in ad-hoc queries.
   Mitigation: centralized repository filters + tests.
5. Risk: environment drift between local/dev/prod.
   Mitigation: single source `.env` contract + startup validation for required variables.

---

This plan is implementation-ready and optimized for the exact evaluation criteria: data integrity, performance, concurrency correctness, and usable frontend behavior.
