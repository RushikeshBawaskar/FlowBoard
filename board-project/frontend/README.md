# Task Flow Frontend

React board UI for Task Flow.

## Stack

- React 19 + TypeScript
- Vite
- `dnd-kit` (`@dnd-kit/core`, `@dnd-kit/sortable`, `@dnd-kit/utilities`)

## Features

- Register/Login with backend JWT auth
- Board selection, create, rename, delete
- Board detail rendering (lists + cards)
- Card create and edit
- Drag-and-drop cards within and across lists using `dnd-kit`
- Optimistic UI move with rollback on API failure

## Local run

From repo root:

1. Install dependencies:
   - `npm install --prefix frontend`
2. Start dev server:
   - `npm run --prefix frontend dev -- --host 127.0.0.1 --port 5173`

Frontend URL:
- `http://127.0.0.1:5173`

## Frontend environment

Optional file: `frontend/.env`

```env
VITE_API_BASE_URL=http://127.0.0.1:8000/api/v1
```

If absent, default is `http://127.0.0.1:8000/api/v1`.

## Runtime behavior

- JWT token is stored in browser `localStorage` and sent as bearer token for board/card APIs.
- Drag flow:
  1. optimistic card reorder in UI
  2. `PATCH /cards/{id}/move`
  3. rollback on failure
  4. refresh board detail on success

## Docker mode

In Docker Compose, frontend is served by Nginx and proxies `/api` to backend.
So production container uses `VITE_API_BASE_URL=/api/v1`.

## Troubleshooting

- 401 errors:
  - Login again (token may be missing/expired).
- Drag change not persisted:
  - Check network tab for `PATCH /cards/{id}/move` response.
- CORS issues in local split mode:
  - Ensure backend `.env` includes frontend origin in `FRONTEND_ORIGINS`.
