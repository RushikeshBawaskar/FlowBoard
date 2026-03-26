import {
  DndContext,
  PointerSensor,
  TouchSensor,
  closestCenter,
  useDroppable,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragOverEvent,
  type DragStartEvent,
} from '@dnd-kit/core'
import { CSS } from '@dnd-kit/utilities'
import {
  SortableContext,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable'
import { useEffect, useMemo, useRef, useState } from 'react'
import './App.css'

type BoardSummary = {
  id: string
  name: string
}

type Card = {
  id: string
  list_id: string
  title: string
  description: string | null
  position_rank: string
}

type List = {
  id: string
  name: string
  position_rank: string
  cards: Card[]
}

type BoardDetail = {
  id: string
  name: string
  lists: List[]
}

type CardMovePayload = {
  target_list_id: string
  prev_card_id: string | null
  next_card_id: string | null
}

type CardMoveResponse = {
  card_id: string
  board_id: string
  list_id: string
}

type AuthResponse = {
  access_token: string
  token_type: string
  user: {
    id: string
    email: string
  }
}

type CardLocation = {
  listIndex: number
  listId: string
  cardIndex: number
}

type ApiErrorItem = {
  loc?: Array<string | number>
  msg?: string
}

const API_BASE_URL =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ??
  'http://127.0.0.1:8000/api/v1'
const AUTH_TOKEN_KEY = 'taskflow_access_token'
const LIST_DROPZONE_PREFIX = 'list-dropzone-'

const listDropzoneId = (listId: string): string => `${LIST_DROPZONE_PREFIX}${listId}`

const normalizeApiError = (detail: unknown): string | null => {
  if (typeof detail === 'string' && detail.trim() !== '') {
    return detail
  }

  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => {
        if (typeof item === 'string') {
          return item
        }
        if (typeof item === 'object' && item !== null) {
          const typed = item as ApiErrorItem
          if (typed.loc !== undefined && typed.msg !== undefined) {
            const location = typed.loc.join('.')
            return `${location}: ${typed.msg}`
          }
          if (typed.msg !== undefined) {
            return typed.msg
          }
        }
        return null
      })
      .filter((item): item is string => item !== null && item.trim() !== '')

    if (messages.length > 0) {
      return messages.join('; ')
    }
  }

  return null
}

const parseErrorResponse = async (response: Response, fallback: string): Promise<string> => {
  const contentType = response.headers.get('content-type') ?? ''
  if (contentType.includes('application/json')) {
    const payload = (await response.json().catch(() => null)) as
      | { detail?: unknown; message?: string }
      | null
    const detail = normalizeApiError(payload?.detail)
    if (detail !== null) {
      return detail
    }
    if (typeof payload?.message === 'string' && payload.message.trim() !== '') {
      return payload.message
    }
  } else {
    const plainText = (await response.text().catch(() => '')).trim()
    if (plainText !== '') {
      return plainText
    }
  }

  if (response.status === 401) {
    return 'Invalid email or password.'
  }
  return fallback
}

const extractListIdFromDropzone = (dropzoneId: string): string | null => {
  if (!dropzoneId.startsWith(LIST_DROPZONE_PREFIX)) {
    return null
  }
  return dropzoneId.slice(LIST_DROPZONE_PREFIX.length)
}

const findCardLocation = (board: BoardDetail, cardId: string): CardLocation | null => {
  for (let listIndex = 0; listIndex < board.lists.length; listIndex += 1) {
    const list = board.lists[listIndex]
    const cardIndex = list.cards.findIndex((card) => card.id === cardId)
    if (cardIndex >= 0) {
      return {
        listIndex,
        listId: list.id,
        cardIndex,
      }
    }
  }
  return null
}

const cloneLists = (board: BoardDetail): List[] =>
  board.lists.map((list) => ({
    ...list,
    cards: [...list.cards],
  }))

const applyDragReorder = (
  board: BoardDetail,
  activeCardId: string,
  overId: string,
  insertAfterOverCard: boolean,
): BoardDetail | null => {
  if (activeCardId === overId) {
    return board
  }

  const activeLocation = findCardLocation(board, activeCardId)
  if (activeLocation === null) {
    return null
  }

  const lists = cloneLists(board)
  const activeList = lists[activeLocation.listIndex]
  const [movingCard] = activeList.cards.splice(activeLocation.cardIndex, 1)
  if (movingCard === undefined) {
    return null
  }

  const droppedListId = extractListIdFromDropzone(overId)
  if (droppedListId !== null) {
    const destinationIndex = lists.findIndex((list) => list.id === droppedListId)
    if (destinationIndex < 0) {
      return null
    }
    const destinationList = lists[destinationIndex]
    destinationList.cards.push({ ...movingCard, list_id: destinationList.id })
    return {
      ...board,
      lists,
    }
  }

  const overLocation = findCardLocation(board, overId)
  if (overLocation === null) {
    return null
  }

  const destinationList = lists[overLocation.listIndex]
  let destinationIndex = overLocation.cardIndex + (insertAfterOverCard ? 1 : 0)
  if (overLocation.listId === activeLocation.listId && destinationIndex > activeLocation.cardIndex) {
    destinationIndex -= 1
  }
  destinationIndex = Math.max(0, Math.min(destinationIndex, destinationList.cards.length))
  destinationList.cards.splice(destinationIndex, 0, { ...movingCard, list_id: destinationList.id })

  return {
    ...board,
    lists,
  }
}

const buildMovePayloadFromBoard = (board: BoardDetail, cardId: string): CardMovePayload | null => {
  const location = findCardLocation(board, cardId)
  if (location === null) {
    return null
  }

  const targetList = board.lists[location.listIndex]
  const prevCardId = location.cardIndex > 0 ? targetList.cards[location.cardIndex - 1].id : null
  const nextCardId =
    location.cardIndex < targetList.cards.length - 1 ? targetList.cards[location.cardIndex + 1].id : null

  return {
    target_list_id: targetList.id,
    prev_card_id: prevCardId,
    next_card_id: nextCardId,
  }
}

const getActiveMidYFromDrag = (event: DragOverEvent | DragEndEvent): number | null => {
  const initialRect = event.active.rect.current.initial
  if (initialRect === undefined || initialRect === null) {
    return null
  }
  return initialRect.top + event.delta.y + initialRect.height / 2
}

type SortableCardProps = {
  card: Card
  disabled: boolean
  onEditCard: (card: Card) => void
}

function SortableCard({ card, disabled, onEditCard }: SortableCardProps) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: card.id,
    disabled,
  })

  return (
    <div
      ref={setNodeRef}
      style={{
        transform: CSS.Transform.toString(transform),
        transition,
        opacity: isDragging ? 0.65 : 1,
      }}
      className="task-card"
      {...attributes}
      {...listeners}
    >
      <div className="task-card-header">
        <h4>{card.title}</h4>
        <button
          type="button"
          className="inline-action"
          onPointerDown={(event) => event.stopPropagation()}
          onClick={(event) => {
            event.stopPropagation()
            onEditCard(card)
          }}
        >
          Edit
        </button>
      </div>
      {card.description !== null ? <p>{card.description}</p> : null}
    </div>
  )
}

type ListColumnProps = {
  list: List
  isMovingCard: boolean
  onCreateCard: (listId: string) => void
  onEditCard: (card: Card) => void
  newCardTitle: string
  onNewCardTitleChange: (listId: string, title: string) => void
}

function ListColumn({
  list,
  isMovingCard,
  onCreateCard,
  onEditCard,
  newCardTitle,
  onNewCardTitleChange,
}: ListColumnProps) {
  const { setNodeRef, isOver } = useDroppable({ id: listDropzoneId(list.id) })

  return (
    <article className={`list-column ${isOver ? 'list-column-over' : ''}`}>
      <header className="list-header">
        <h3>{list.name}</h3>
        <span>{list.cards.length} cards</span>
      </header>

      <div className="card-create-row">
        <input
          placeholder="Add card title"
          value={newCardTitle}
          onChange={(event) => onNewCardTitleChange(list.id, event.target.value)}
        />
        <button type="button" onClick={() => onCreateCard(list.id)}>
          Add
        </button>
      </div>

      <div ref={setNodeRef} className="card-stack">
        <SortableContext items={list.cards.map((card) => card.id)} strategy={verticalListSortingStrategy}>
          {list.cards.map((card) => (
            <SortableCard
              key={card.id}
              card={card}
              disabled={isMovingCard}
              onEditCard={onEditCard}
            />
          ))}
        </SortableContext>
        {list.cards.length === 0 ? <p className="empty-list">Drop cards here.</p> : null}
      </div>
    </article>
  )
}

function App() {
  const [boards, setBoards] = useState<BoardSummary[]>([])
  const [selectedBoardId, setSelectedBoardId] = useState<string | null>(null)
  const [boardDetail, setBoardDetail] = useState<BoardDetail | null>(null)

  const [authToken, setAuthToken] = useState<string | null>(() => localStorage.getItem(AUTH_TOKEN_KEY))
  const [authEmail, setAuthEmail] = useState('')
  const [authPassword, setAuthPassword] = useState('')
  const [isAuthenticating, setIsAuthenticating] = useState(false)

  const [isLoading, setIsLoading] = useState(false)
  const [isSeeding, setIsSeeding] = useState(false)
  const [isCreatingBoard, setIsCreatingBoard] = useState(false)
  const [isUpdatingBoard, setIsUpdatingBoard] = useState(false)
  const [isDeletingBoard, setIsDeletingBoard] = useState(false)
  const [isMovingCard, setIsMovingCard] = useState(false)
  const [isCreatingCard, setIsCreatingCard] = useState(false)

  const [newBoardName, setNewBoardName] = useState('')
  const [renameBoardName, setRenameBoardName] = useState('')
  const [newCardTitleByList, setNewCardTitleByList] = useState<Record<string, string>>({})
  const [error, setError] = useState<string | null>(null)

  const [activeCardId, setActiveCardId] = useState<string | null>(null)
  const [dragSnapshot, setDragSnapshot] = useState<BoardDetail | null>(null)
  const lastOverKeyRef = useRef<string | null>(null)
  const boardFetchVersionRef = useRef(0)

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 4 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 120, tolerance: 8 } }),
  )

  const hasBoard = useMemo(() => boardDetail !== null, [boardDetail])

  const authHeaders = (includeContentType = false): HeadersInit => {
    const headers: Record<string, string> = {}
    if (includeContentType) {
      headers['Content-Type'] = 'application/json'
    }
    if (authToken !== null) {
      headers.Authorization = `Bearer ${authToken}`
    }
    return headers
  }

  const fetchBoards = async () => {
    const response = await fetch(`${API_BASE_URL}/boards`, {
      headers: authHeaders(),
      cache: 'no-store',
    })
    if (response.status === 401) {
      handleLogout()
      throw new Error('Session expired. Please login again.')
    }
    if (!response.ok) {
      throw new Error(await parseErrorResponse(response, 'Failed to load boards.'))
    }
    const data = (await response.json()) as BoardSummary[]
    setBoards(data)
    if (data.length === 0) {
      setSelectedBoardId(null)
      setBoardDetail(null)
      return
    }
    setSelectedBoardId((previous) => {
      if (previous === null) {
        return data[0].id
      }
      const exists = data.some((board) => board.id === previous)
      return exists ? previous : data[0].id
    })
  }

  const fetchBoardDetail = async (boardId: string, cacheBuster?: string) => {
    const fetchVersion = boardFetchVersionRef.current + 1
    boardFetchVersionRef.current = fetchVersion
    const url =
      cacheBuster === undefined
        ? `${API_BASE_URL}/boards/${boardId}`
        : `${API_BASE_URL}/boards/${boardId}?_=${encodeURIComponent(cacheBuster)}`
    const response = await fetch(url, {
      headers: authHeaders(),
      cache: 'no-store',
    })
    if (response.status === 401) {
      handleLogout()
      throw new Error('Session expired. Please login again.')
    }
    if (!response.ok) {
      throw new Error(await parseErrorResponse(response, 'Failed to load board details.'))
    }
    const data = (await response.json()) as BoardDetail
    if (boardFetchVersionRef.current !== fetchVersion) {
      return
    }
    setBoardDetail(data)
  }

  const loadData = async () => {
    if (authToken === null) {
      return
    }

    try {
      setIsLoading(true)
      setError(null)
      await fetchBoards()
    } catch (fetchError) {
      setError(fetchError instanceof Error ? fetchError.message : 'Unknown error while loading boards.')
    } finally {
      setIsLoading(false)
    }
  }

  const persistToken = (token: string) => {
    localStorage.setItem(AUTH_TOKEN_KEY, token)
    setAuthToken(token)
  }

  const handleRegisterOrLogin = async (mode: 'register' | 'login') => {
    if (authEmail.trim() === '' || authPassword.trim() === '') {
      setError('Email and password are required.')
      return
    }

    try {
      setIsAuthenticating(true)
      setError(null)
      const response = await fetch(`${API_BASE_URL}/auth/${mode}`, {
        method: 'POST',
        headers: authHeaders(true),
        body: JSON.stringify({
          email: authEmail.trim().toLowerCase(),
          password: authPassword,
        }),
      })

      if (!response.ok) {
        throw new Error(await parseErrorResponse(response, `Failed to ${mode}.`))
      }

      const data = (await response.json()) as AuthResponse
      persistToken(data.access_token)
      setAuthPassword('')
      await loadData()
    } catch (authError) {
      setError(authError instanceof Error ? authError.message : 'Authentication failed.')
    } finally {
      setIsAuthenticating(false)
    }
  }

  const handleLogout = () => {
    localStorage.removeItem(AUTH_TOKEN_KEY)
    boardFetchVersionRef.current += 1
    setAuthToken(null)
    setBoards([])
    setSelectedBoardId(null)
    setBoardDetail(null)
    setError(null)
  }

  const handleSeedDemoData = async () => {
    if (authToken === null) {
      return
    }

    try {
      setIsSeeding(true)
      setError(null)
      const response = await fetch(`${API_BASE_URL}/boards/demo-seed`, {
        method: 'POST',
        headers: authHeaders(),
      })
      if (!response.ok) {
        throw new Error(await parseErrorResponse(response, 'Failed to seed demo data.'))
      }
      const seededBoard = (await response.json()) as BoardDetail
      await fetchBoards()
      setSelectedBoardId(seededBoard.id)
      setBoardDetail(seededBoard)
    } catch (seedError) {
      setError(seedError instanceof Error ? seedError.message : 'Unknown error while creating demo board.')
    } finally {
      setIsSeeding(false)
    }
  }

  const handleCreateBoard = async () => {
    if (newBoardName.trim() === '') {
      setError('Board name is required.')
      return
    }

    try {
      setIsCreatingBoard(true)
      setError(null)
      const response = await fetch(`${API_BASE_URL}/boards`, {
        method: 'POST',
        headers: authHeaders(true),
        body: JSON.stringify({ name: newBoardName.trim() }),
      })
      if (!response.ok) {
        throw new Error(await parseErrorResponse(response, 'Failed to create board.'))
      }
      const createdBoard = (await response.json()) as BoardDetail
      await fetchBoards()
      setSelectedBoardId(createdBoard.id)
      setBoardDetail(createdBoard)
      setNewBoardName('')
    } catch (createError) {
      setError(createError instanceof Error ? createError.message : 'Unknown error while creating board.')
    } finally {
      setIsCreatingBoard(false)
    }
  }

  const handleRenameBoard = async () => {
    if (selectedBoardId === null || renameBoardName.trim() === '') {
      setError('Board name is required.')
      return
    }

    try {
      setIsUpdatingBoard(true)
      setError(null)
      const response = await fetch(`${API_BASE_URL}/boards/${selectedBoardId}`, {
        method: 'PATCH',
        headers: authHeaders(true),
        body: JSON.stringify({ name: renameBoardName.trim() }),
      })
      if (!response.ok) {
        throw new Error(await parseErrorResponse(response, 'Failed to rename board.'))
      }
      const updatedBoard = (await response.json()) as BoardDetail
      await fetchBoards()
      setBoardDetail(updatedBoard)
    } catch (updateError) {
      setError(updateError instanceof Error ? updateError.message : 'Unknown error while renaming board.')
    } finally {
      setIsUpdatingBoard(false)
    }
  }

  const handleDeleteBoard = async () => {
    if (selectedBoardId === null) {
      return
    }
    const shouldDelete = window.confirm('Delete this board? This performs a soft delete.')
    if (!shouldDelete) {
      return
    }

    try {
      setIsDeletingBoard(true)
      setError(null)
      const response = await fetch(`${API_BASE_URL}/boards/${selectedBoardId}`, {
        method: 'DELETE',
        headers: authHeaders(),
      })
      if (!response.ok) {
        throw new Error(await parseErrorResponse(response, 'Failed to delete board.'))
      }
      await fetchBoards()
      setBoardDetail(null)
    } catch (deleteError) {
      setError(deleteError instanceof Error ? deleteError.message : 'Unknown error while deleting board.')
    } finally {
      setIsDeletingBoard(false)
    }
  }

  const handleCreateCard = async (listId: string) => {
    const title = (newCardTitleByList[listId] ?? '').trim()
    if (title === '') {
      setError('Card title is required.')
      return
    }

    if (selectedBoardId === null) {
      return
    }

    try {
      setIsCreatingCard(true)
      setError(null)
      const response = await fetch(`${API_BASE_URL}/cards`, {
        method: 'POST',
        headers: authHeaders(true),
        body: JSON.stringify({
          list_id: listId,
          title,
          description: null,
        }),
      })
      if (!response.ok) {
        throw new Error(await parseErrorResponse(response, 'Failed to create card.'))
      }

      setNewCardTitleByList((previous) => ({
        ...previous,
        [listId]: '',
      }))
      await fetchBoardDetail(selectedBoardId)
    } catch (createError) {
      setError(createError instanceof Error ? createError.message : 'Unknown error while creating card.')
    } finally {
      setIsCreatingCard(false)
    }
  }

  const handleEditCard = async (card: Card) => {
    const title = window.prompt('Card title', card.title)
    if (title === null) {
      return
    }
    const description = window.prompt('Card description (optional)', card.description ?? '')
    if (description === null) {
      return
    }

    if (selectedBoardId === null) {
      return
    }

    try {
      setError(null)
      const response = await fetch(`${API_BASE_URL}/cards/${card.id}`, {
        method: 'PATCH',
        headers: authHeaders(true),
        body: JSON.stringify({
          title,
          description: description.trim() === '' ? null : description,
        }),
      })
      if (!response.ok) {
        throw new Error(await parseErrorResponse(response, 'Failed to update card.'))
      }
      await fetchBoardDetail(selectedBoardId)
    } catch (editError) {
      setError(editError instanceof Error ? editError.message : 'Unknown error while editing card.')
    }
  }

  const executeMove = async (payload: CardMovePayload, cardId: string): Promise<CardMoveResponse> => {
    const response = await fetch(`${API_BASE_URL}/cards/${cardId}/move`, {
      method: 'PATCH',
      headers: authHeaders(true),
      body: JSON.stringify(payload),
    })
    if (!response.ok) {
      throw new Error(await parseErrorResponse(response, 'Failed to move card.'))
    }
    return (await response.json()) as CardMoveResponse
  }

  const handleDragStart = (event: DragStartEvent) => {
    if (boardDetail === null || isMovingCard) {
      return
    }
    setActiveCardId(String(event.active.id))
    setDragSnapshot(boardDetail)
    lastOverKeyRef.current = null
  }

  const handleDragOver = (event: DragOverEvent) => {
    if (boardDetail === null || activeCardId === null || event.over === null) {
      return
    }

    const overId = String(event.over.id)
    const overRectMidY = event.over.rect.top + event.over.rect.height / 2
    const activeRectMidY = getActiveMidYFromDrag(event)
    const isOverListDropzone = extractListIdFromDropzone(overId) !== null
    const insertAfterOverCard = !isOverListDropzone && activeRectMidY !== null && activeRectMidY > overRectMidY
    const overKey = `${overId}:${insertAfterOverCard ? "after" : "before"}`
    if (lastOverKeyRef.current === overKey) {
      return
    }
    lastOverKeyRef.current = overKey

    const nextBoard = applyDragReorder(boardDetail, activeCardId, overId, insertAfterOverCard)
    if (nextBoard !== null) {
      setBoardDetail(nextBoard)
    }
  }

  const clearDragState = () => {
    setActiveCardId(null)
    setDragSnapshot(null)
    lastOverKeyRef.current = null
  }

  const handleDragCancel = () => {
    if (dragSnapshot !== null) {
      setBoardDetail(dragSnapshot)
    }
    clearDragState()
  }

  const handleDragEnd = async (event: DragEndEvent) => {
    if (boardDetail === null || activeCardId === null) {
      clearDragState()
      return
    }

    const over = event.over
    const overId = over?.id != null ? String(over.id) : null
    if (overId === null || over === null) {
      if (dragSnapshot !== null) {
        setBoardDetail(dragSnapshot)
      }
      clearDragState()
      return
    }

    const overRectMidY = over.rect.top + over.rect.height / 2
    const activeRectMidY = getActiveMidYFromDrag(event)
    const isOverListDropzone = extractListIdFromDropzone(overId) !== null
    const insertAfterOverCard = !isOverListDropzone && activeRectMidY !== null && activeRectMidY > overRectMidY

    const baselineBoard = dragSnapshot ?? boardDetail
    const finalBoard =
      applyDragReorder(baselineBoard, activeCardId, overId, insertAfterOverCard) ?? boardDetail
    setBoardDetail(finalBoard)

    const payload = buildMovePayloadFromBoard(finalBoard, activeCardId)
    if (payload === null) {
      if (dragSnapshot !== null) {
        setBoardDetail(dragSnapshot)
      }
      clearDragState()
      return
    }

    try {
      setIsMovingCard(true)
      setError(null)
      const moveResult = await executeMove(payload, activeCardId)
      if (selectedBoardId !== null) {
        try {
          await fetchBoardDetail(selectedBoardId, `${Date.now()}-${moveResult.card_id}`)
        } catch (refreshError) {
          setError(
            refreshError instanceof Error
              ? `Move saved, but refresh failed: ${refreshError.message}`
              : 'Move saved, but refresh failed.',
          )
        }
      }
    } catch (moveError) {
      if (dragSnapshot !== null) {
        setBoardDetail(dragSnapshot)
      }
      setError(moveError instanceof Error ? moveError.message : 'Unknown error while moving card.')
    } finally {
      setIsMovingCard(false)
      clearDragState()
    }
  }

  useEffect(() => {
    if (authToken === null) {
      return
    }
    void loadData()
  }, [authToken])

  useEffect(() => {
    if (authToken === null || selectedBoardId === null) {
      return
    }

    const loadSelectedBoard = async () => {
      try {
        setIsLoading(true)
        setError(null)
        await fetchBoardDetail(selectedBoardId)
      } catch (detailError) {
        setError(
          detailError instanceof Error
            ? detailError.message
            : 'Unknown error while loading board detail.',
        )
      } finally {
        setIsLoading(false)
      }
    }

    void loadSelectedBoard()
  }, [authToken, selectedBoardId])

  useEffect(() => {
    if (boardDetail === null) {
      setRenameBoardName('')
      return
    }
    setRenameBoardName(boardDetail.name)
  }, [boardDetail?.id, boardDetail?.name])

  return (
    <main className="page">
      <header className="top-bar">
        <div>
          <p className="eyebrow">Task Flow</p>
          <h1>Board View</h1>
          <p className="subtext">
            dnd-kit drag-and-drop with optimistic UI, rollback, and JWT-protected API calls.
          </p>
        </div>
        <div className="actions">
          <button type="button" onClick={() => void loadData()} disabled={isLoading || authToken === null}>
            Refresh
          </button>
          <button
            type="button"
            onClick={() => void handleSeedDemoData()}
            disabled={isSeeding || authToken === null}
          >
            {isSeeding ? 'Seeding...' : 'Load Demo Data'}
          </button>
          {authToken !== null ? (
            <button type="button" onClick={handleLogout}>
              Logout
            </button>
          ) : null}
        </div>
      </header>

      {error !== null ? <p className="message error">{error}</p> : null}

      {authToken === null ? (
        <section className="auth-box">
          <h2>Login or Register</h2>
          <p>Use your email/password. Register creates a new account and returns JWT.</p>
          <div className="auth-controls">
            <input
              value={authEmail}
              onChange={(event) => setAuthEmail(event.target.value)}
              placeholder="Email"
              type="email"
            />
            <input
              value={authPassword}
              onChange={(event) => setAuthPassword(event.target.value)}
              placeholder="Password (min 8 chars)"
              type="password"
            />
            <button
              type="button"
              disabled={isAuthenticating}
              onClick={() => void handleRegisterOrLogin('register')}
            >
              {isAuthenticating ? 'Please wait...' : 'Register'}
            </button>
            <button
              type="button"
              disabled={isAuthenticating}
              onClick={() => void handleRegisterOrLogin('login')}
            >
              {isAuthenticating ? 'Please wait...' : 'Login'}
            </button>
          </div>
        </section>
      ) : null}

      {authToken !== null ? (
        <>
          <section className="controls">
            <label htmlFor="board-select">Board</label>
            <select
              id="board-select"
              value={selectedBoardId ?? ''}
              onChange={(event) => setSelectedBoardId(event.target.value || null)}
              disabled={boards.length === 0}
            >
              {boards.length === 0 ? <option value="">No boards available</option> : null}
              {boards.map((board) => (
                <option key={board.id} value={board.id}>
                  {board.name}
                </option>
              ))}
            </select>
          </section>

          <section className="create-board">
            <label htmlFor="new-board-name">Create Board</label>
            <div className="create-board-controls">
              <input
                id="new-board-name"
                value={newBoardName}
                onChange={(event) => setNewBoardName(event.target.value)}
                placeholder="Board name"
              />
              <button type="button" onClick={() => void handleCreateBoard()} disabled={isCreatingBoard}>
                {isCreatingBoard ? 'Creating...' : 'Create'}
              </button>
            </div>
          </section>

          {hasBoard ? (
            <section className="create-board">
              <label htmlFor="rename-board-name">Rename / Delete Board</label>
              <div className="create-board-controls">
                <input
                  id="rename-board-name"
                  value={renameBoardName}
                  onChange={(event) => setRenameBoardName(event.target.value)}
                />
                <button type="button" onClick={() => void handleRenameBoard()} disabled={isUpdatingBoard}>
                  {isUpdatingBoard ? 'Saving...' : 'Rename'}
                </button>
                <button type="button" onClick={() => void handleDeleteBoard()} disabled={isDeletingBoard}>
                  {isDeletingBoard ? 'Deleting...' : 'Delete'}
                </button>
              </div>
            </section>
          ) : null}

          {isLoading ? <p className="message">Loading board...</p> : null}
          {isMovingCard ? <p className="message">Saving move...</p> : null}
          {isCreatingCard ? <p className="message">Creating card...</p> : null}

          {!isLoading && !hasBoard ? (
            <section className="empty-state">
              <h2>No board data yet</h2>
              <p>Click "Load Demo Data" or create your first board above.</p>
            </section>
          ) : null}

          {!isLoading && boardDetail !== null ? (
            <section>
              <h2 className="board-title">{boardDetail.name}</h2>

              <DndContext
                sensors={sensors}
                collisionDetection={closestCenter}
                onDragStart={handleDragStart}
                onDragOver={handleDragOver}
                onDragCancel={handleDragCancel}
                onDragEnd={(event) => {
                  void handleDragEnd(event)
                }}
              >
                <div className="board-grid">
                  {boardDetail.lists.map((list) => (
                    <ListColumn
                      key={list.id}
                      list={list}
                      isMovingCard={isMovingCard}
                      onCreateCard={(listId) => {
                        void handleCreateCard(listId)
                      }}
                      onEditCard={(card) => {
                        void handleEditCard(card)
                      }}
                      newCardTitle={newCardTitleByList[list.id] ?? ''}
                      onNewCardTitleChange={(listId, title) => {
                        setNewCardTitleByList((previous) => ({
                          ...previous,
                          [listId]: title,
                        }))
                      }}
                    />
                  ))}
                </div>
              </DndContext>
            </section>
          ) : null}
        </>
      ) : null}
    </main>
  )
}

export default App
