from __future__ import annotations

import os
import uuid

import httpx
import pytest

API_BASE_URL = os.getenv("TASKFLOW_API_BASE_URL", "http://127.0.0.1:8000/api/v1")
TEST_PASSWORD = "test-pass-123"


def _unique_email(prefix: str) -> str:
    return f"{prefix}.{uuid.uuid4().hex[:10]}@example.com"


async def _register_user(client: httpx.AsyncClient, *, prefix: str) -> dict[str, str]:
    response = await client.post(
        "/auth/register",
        json={"email": _unique_email(prefix), "password": TEST_PASSWORD},
    )
    assert response.status_code == 201, response.text
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def _create_board(client: httpx.AsyncClient, headers: dict[str, str], *, name: str) -> dict:
    response = await client.post("/boards", headers=headers, json={"name": name})
    assert response.status_code == 201, response.text
    return response.json()


async def _create_card(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    *,
    list_id: str,
    title: str,
) -> dict:
    response = await client.post(
        "/cards",
        headers=headers,
        json={"list_id": list_id, "title": title, "description": None},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _move_card(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    *,
    card_id: str,
    target_list_id: str,
    prev_card_id: str | None,
    next_card_id: str | None,
) -> dict:
    response = await client.patch(
        f"/cards/{card_id}/move",
        headers=headers,
        json={
            "target_list_id": target_list_id,
            "prev_card_id": prev_card_id,
            "next_card_id": next_card_id,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


async def _fetch_board(client: httpx.AsyncClient, headers: dict[str, str], board_id: str) -> dict:
    response = await client.get(f"/boards/{board_id}", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def _list_by_id(board: dict, list_id: str) -> dict:
    for item in board["lists"]:
        if item["id"] == list_id:
            return item
    raise AssertionError(f"List not found: {list_id}")


def _card_id_by_title(list_payload: dict, title: str) -> str:
    for card in list_payload["cards"]:
        if card["title"] == title:
            return card["id"]
    raise AssertionError(f"Card not found: {title}")


def _assert_list_titles(board: dict, list_id: str, expected_titles: list[str]) -> None:
    payload = _list_by_id(board, list_id)
    actual_titles = [card["title"] for card in payload["cards"]]
    assert actual_titles == expected_titles


def _assert_board_card_integrity(board: dict) -> None:
    all_ids = [card["id"] for list_payload in board["lists"] for card in list_payload["cards"]]
    assert len(all_ids) == len(set(all_ids)), "Duplicate card IDs found across board lists."


@pytest.mark.asyncio
async def test_move_same_list_top_middle_bottom() -> None:
    async with httpx.AsyncClient(base_url=API_BASE_URL, timeout=20) as client:
        headers = await _register_user(client, prefix="move.same")
        board = await _create_board(client, headers, name="Move Same List Board")
        board_id = board["id"]
        todo_list_id = board["lists"][0]["id"]

        await _create_card(client, headers, list_id=todo_list_id, title="A")
        await _create_card(client, headers, list_id=todo_list_id, title="B")
        await _create_card(client, headers, list_id=todo_list_id, title="C")
        await _create_card(client, headers, list_id=todo_list_id, title="D")

        board = await _fetch_board(client, headers, board_id)
        _assert_list_titles(board, todo_list_id, ["A", "B", "C", "D"])

        todo = _list_by_id(board, todo_list_id)
        a_id = _card_id_by_title(todo, "A")
        d_id = _card_id_by_title(todo, "D")
        await _move_card(
            client,
            headers,
            card_id=d_id,
            target_list_id=todo_list_id,
            prev_card_id=None,
            next_card_id=a_id,
        )
        board = await _fetch_board(client, headers, board_id)
        _assert_list_titles(board, todo_list_id, ["D", "A", "B", "C"])

        todo = _list_by_id(board, todo_list_id)
        d_id = _card_id_by_title(todo, "D")
        b_id = _card_id_by_title(todo, "B")
        c_id = _card_id_by_title(todo, "C")
        await _move_card(
            client,
            headers,
            card_id=d_id,
            target_list_id=todo_list_id,
            prev_card_id=b_id,
            next_card_id=c_id,
        )
        board = await _fetch_board(client, headers, board_id)
        _assert_list_titles(board, todo_list_id, ["A", "B", "D", "C"])

        todo = _list_by_id(board, todo_list_id)
        d_id = _card_id_by_title(todo, "D")
        c_id = _card_id_by_title(todo, "C")
        await _move_card(
            client,
            headers,
            card_id=d_id,
            target_list_id=todo_list_id,
            prev_card_id=c_id,
            next_card_id=None,
        )
        board = await _fetch_board(client, headers, board_id)
        _assert_list_titles(board, todo_list_id, ["A", "B", "C", "D"])


@pytest.mark.asyncio
async def test_move_across_lists_top_middle_bottom() -> None:
    async with httpx.AsyncClient(base_url=API_BASE_URL, timeout=20) as client:
        headers = await _register_user(client, prefix="move.cross")
        board = await _create_board(client, headers, name="Move Cross List Board")
        board_id = board["id"]
        todo_list_id = board["lists"][0]["id"]
        in_progress_list_id = board["lists"][1]["id"]

        await _create_card(client, headers, list_id=todo_list_id, title="T1")
        await _create_card(client, headers, list_id=todo_list_id, title="T2")
        await _create_card(client, headers, list_id=in_progress_list_id, title="P1")
        await _create_card(client, headers, list_id=in_progress_list_id, title="P2")

        board = await _fetch_board(client, headers, board_id)
        _assert_list_titles(board, todo_list_id, ["T1", "T2"])
        _assert_list_titles(board, in_progress_list_id, ["P1", "P2"])

        todo = _list_by_id(board, todo_list_id)
        target = _list_by_id(board, in_progress_list_id)
        t2_id = _card_id_by_title(todo, "T2")
        p1_id = _card_id_by_title(target, "P1")
        await _move_card(
            client,
            headers,
            card_id=t2_id,
            target_list_id=in_progress_list_id,
            prev_card_id=None,
            next_card_id=p1_id,
        )
        board = await _fetch_board(client, headers, board_id)
        _assert_list_titles(board, todo_list_id, ["T1"])
        _assert_list_titles(board, in_progress_list_id, ["T2", "P1", "P2"])

        todo = _list_by_id(board, todo_list_id)
        target = _list_by_id(board, in_progress_list_id)
        t1_id = _card_id_by_title(todo, "T1")
        p2_id = _card_id_by_title(target, "P2")
        await _move_card(
            client,
            headers,
            card_id=t1_id,
            target_list_id=in_progress_list_id,
            prev_card_id=p2_id,
            next_card_id=None,
        )
        board = await _fetch_board(client, headers, board_id)
        _assert_list_titles(board, todo_list_id, [])
        _assert_list_titles(board, in_progress_list_id, ["T2", "P1", "P2", "T1"])

        target = _list_by_id(board, in_progress_list_id)
        p1_id = _card_id_by_title(target, "P1")
        p2_id = _card_id_by_title(target, "P2")
        t1_id = _card_id_by_title(target, "T1")
        await _move_card(
            client,
            headers,
            card_id=p1_id,
            target_list_id=in_progress_list_id,
            prev_card_id=p2_id,
            next_card_id=t1_id,
        )
        board = await _fetch_board(client, headers, board_id)
        _assert_list_titles(board, in_progress_list_id, ["T2", "P2", "P1", "T1"])


@pytest.mark.asyncio
async def test_repeated_moves_stay_consistent() -> None:
    async with httpx.AsyncClient(base_url=API_BASE_URL, timeout=20) as client:
        headers = await _register_user(client, prefix="move.repeat")
        board = await _create_board(client, headers, name="Move Repeat Board")
        board_id = board["id"]
        todo_list_id = board["lists"][0]["id"]
        in_progress_list_id = board["lists"][1]["id"]

        await _create_card(client, headers, list_id=todo_list_id, title="MOVER")
        await _create_card(client, headers, list_id=todo_list_id, title="KEEP1")
        await _create_card(client, headers, list_id=todo_list_id, title="KEEP2")
        await _create_card(client, headers, list_id=in_progress_list_id, title="IP1")

        for iteration in range(1, 21):
            board = await _fetch_board(client, headers, board_id)
            todo = _list_by_id(board, todo_list_id)
            in_progress = _list_by_id(board, in_progress_list_id)

            mover_in_todo = any(card["title"] == "MOVER" for card in todo["cards"])
            if mover_in_todo:
                next_card_id = in_progress["cards"][0]["id"] if len(in_progress["cards"]) > 0 else None
                await _move_card(
                    client,
                    headers,
                    card_id=_card_id_by_title(todo, "MOVER"),
                    target_list_id=in_progress_list_id,
                    prev_card_id=None,
                    next_card_id=next_card_id,
                )
            else:
                prev_card_id = todo["cards"][-1]["id"] if len(todo["cards"]) > 0 else None
                await _move_card(
                    client,
                    headers,
                    card_id=_card_id_by_title(in_progress, "MOVER"),
                    target_list_id=todo_list_id,
                    prev_card_id=prev_card_id,
                    next_card_id=None,
                )

            board = await _fetch_board(client, headers, board_id)
            all_cards = [card["id"] for list_payload in board["lists"] for card in list_payload["cards"]]
            assert len(all_cards) == len(set(all_cards)), f"Duplicate card IDs after iteration {iteration}"
            mover_count = sum(
                1
                for list_payload in board["lists"]
                for card in list_payload["cards"]
                if card["title"] == "MOVER"
            )
            assert mover_count == 1, f"MOVER card count mismatch after iteration {iteration}"


@pytest.mark.asyncio
async def test_move_with_empty_target_list_and_back() -> None:
    async with httpx.AsyncClient(base_url=API_BASE_URL, timeout=20) as client:
        headers = await _register_user(client, prefix="move.empty")
        board = await _create_board(client, headers, name="Move Empty List Board")
        board_id = board["id"]
        todo_list_id = board["lists"][0]["id"]
        in_progress_list_id = board["lists"][1]["id"]

        await _create_card(client, headers, list_id=todo_list_id, title="A")
        await _create_card(client, headers, list_id=todo_list_id, title="B")
        await _create_card(client, headers, list_id=todo_list_id, title="C")

        board = await _fetch_board(client, headers, board_id)
        _assert_list_titles(board, todo_list_id, ["A", "B", "C"])
        _assert_list_titles(board, in_progress_list_id, [])

        todo = _list_by_id(board, todo_list_id)
        b_id = _card_id_by_title(todo, "B")
        await _move_card(
            client,
            headers,
            card_id=b_id,
            target_list_id=in_progress_list_id,
            prev_card_id=None,
            next_card_id=None,
        )
        board = await _fetch_board(client, headers, board_id)
        _assert_list_titles(board, todo_list_id, ["A", "C"])
        _assert_list_titles(board, in_progress_list_id, ["B"])
        _assert_board_card_integrity(board)

        todo = _list_by_id(board, todo_list_id)
        in_progress = _list_by_id(board, in_progress_list_id)
        a_id = _card_id_by_title(todo, "A")
        b_id = _card_id_by_title(in_progress, "B")
        await _move_card(
            client,
            headers,
            card_id=a_id,
            target_list_id=in_progress_list_id,
            prev_card_id=None,
            next_card_id=b_id,
        )
        board = await _fetch_board(client, headers, board_id)
        _assert_list_titles(board, todo_list_id, ["C"])
        _assert_list_titles(board, in_progress_list_id, ["A", "B"])
        _assert_board_card_integrity(board)

        todo = _list_by_id(board, todo_list_id)
        in_progress = _list_by_id(board, in_progress_list_id)
        c_id = _card_id_by_title(todo, "C")
        b_id = _card_id_by_title(in_progress, "B")
        await _move_card(
            client,
            headers,
            card_id=c_id,
            target_list_id=in_progress_list_id,
            prev_card_id=b_id,
            next_card_id=None,
        )
        board = await _fetch_board(client, headers, board_id)
        _assert_list_titles(board, todo_list_id, [])
        _assert_list_titles(board, in_progress_list_id, ["A", "B", "C"])
        _assert_board_card_integrity(board)

        in_progress = _list_by_id(board, in_progress_list_id)
        c_id = _card_id_by_title(in_progress, "C")
        await _move_card(
            client,
            headers,
            card_id=c_id,
            target_list_id=todo_list_id,
            prev_card_id=None,
            next_card_id=None,
        )
        board = await _fetch_board(client, headers, board_id)
        _assert_list_titles(board, todo_list_id, ["C"])
        _assert_list_titles(board, in_progress_list_id, ["A", "B"])
        _assert_board_card_integrity(board)


@pytest.mark.asyncio
async def test_mixed_move_sequence_top_middle_bottom_across_lists() -> None:
    async with httpx.AsyncClient(base_url=API_BASE_URL, timeout=20) as client:
        headers = await _register_user(client, prefix="move.mixed")
        board = await _create_board(client, headers, name="Move Mixed Sequence Board")
        board_id = board["id"]
        todo_list_id = board["lists"][0]["id"]
        in_progress_list_id = board["lists"][1]["id"]

        await _create_card(client, headers, list_id=todo_list_id, title="A")
        await _create_card(client, headers, list_id=todo_list_id, title="B")
        await _create_card(client, headers, list_id=todo_list_id, title="C")
        await _create_card(client, headers, list_id=todo_list_id, title="D")

        board = await _fetch_board(client, headers, board_id)
        _assert_list_titles(board, todo_list_id, ["A", "B", "C", "D"])
        _assert_list_titles(board, in_progress_list_id, [])

        todo = _list_by_id(board, todo_list_id)
        c_id = _card_id_by_title(todo, "C")
        await _move_card(
            client,
            headers,
            card_id=c_id,
            target_list_id=in_progress_list_id,
            prev_card_id=None,
            next_card_id=None,
        )
        board = await _fetch_board(client, headers, board_id)
        _assert_list_titles(board, todo_list_id, ["A", "B", "D"])
        _assert_list_titles(board, in_progress_list_id, ["C"])
        _assert_board_card_integrity(board)

        todo = _list_by_id(board, todo_list_id)
        in_progress = _list_by_id(board, in_progress_list_id)
        a_id = _card_id_by_title(todo, "A")
        c_id = _card_id_by_title(in_progress, "C")
        await _move_card(
            client,
            headers,
            card_id=a_id,
            target_list_id=in_progress_list_id,
            prev_card_id=None,
            next_card_id=c_id,
        )
        board = await _fetch_board(client, headers, board_id)
        _assert_list_titles(board, todo_list_id, ["B", "D"])
        _assert_list_titles(board, in_progress_list_id, ["A", "C"])
        _assert_board_card_integrity(board)

        todo = _list_by_id(board, todo_list_id)
        in_progress = _list_by_id(board, in_progress_list_id)
        d_id = _card_id_by_title(todo, "D")
        a_id = _card_id_by_title(in_progress, "A")
        c_id = _card_id_by_title(in_progress, "C")
        await _move_card(
            client,
            headers,
            card_id=d_id,
            target_list_id=in_progress_list_id,
            prev_card_id=a_id,
            next_card_id=c_id,
        )
        board = await _fetch_board(client, headers, board_id)
        _assert_list_titles(board, todo_list_id, ["B"])
        _assert_list_titles(board, in_progress_list_id, ["A", "D", "C"])
        _assert_board_card_integrity(board)

        todo = _list_by_id(board, todo_list_id)
        in_progress = _list_by_id(board, in_progress_list_id)
        b_id = _card_id_by_title(todo, "B")
        c_id = _card_id_by_title(in_progress, "C")
        await _move_card(
            client,
            headers,
            card_id=b_id,
            target_list_id=in_progress_list_id,
            prev_card_id=c_id,
            next_card_id=None,
        )
        board = await _fetch_board(client, headers, board_id)
        _assert_list_titles(board, todo_list_id, [])
        _assert_list_titles(board, in_progress_list_id, ["A", "D", "C", "B"])
        _assert_board_card_integrity(board)

        in_progress = _list_by_id(board, in_progress_list_id)
        d_id = _card_id_by_title(in_progress, "D")
        await _move_card(
            client,
            headers,
            card_id=d_id,
            target_list_id=todo_list_id,
            prev_card_id=None,
            next_card_id=None,
        )
        board = await _fetch_board(client, headers, board_id)
        _assert_list_titles(board, todo_list_id, ["D"])
        _assert_list_titles(board, in_progress_list_id, ["A", "C", "B"])
        _assert_board_card_integrity(board)

        todo = _list_by_id(board, todo_list_id)
        in_progress = _list_by_id(board, in_progress_list_id)
        a_id = _card_id_by_title(in_progress, "A")
        d_id = _card_id_by_title(todo, "D")
        await _move_card(
            client,
            headers,
            card_id=a_id,
            target_list_id=todo_list_id,
            prev_card_id=None,
            next_card_id=d_id,
        )
        board = await _fetch_board(client, headers, board_id)
        _assert_list_titles(board, todo_list_id, ["A", "D"])
        _assert_list_titles(board, in_progress_list_id, ["C", "B"])
        _assert_board_card_integrity(board)

        todo = _list_by_id(board, todo_list_id)
        in_progress = _list_by_id(board, in_progress_list_id)
        b_id = _card_id_by_title(in_progress, "B")
        a_id = _card_id_by_title(todo, "A")
        d_id = _card_id_by_title(todo, "D")
        await _move_card(
            client,
            headers,
            card_id=b_id,
            target_list_id=todo_list_id,
            prev_card_id=a_id,
            next_card_id=d_id,
        )
        board = await _fetch_board(client, headers, board_id)
        _assert_list_titles(board, todo_list_id, ["A", "B", "D"])
        _assert_list_titles(board, in_progress_list_id, ["C"])
        _assert_board_card_integrity(board)

        in_progress = _list_by_id(board, in_progress_list_id)
        todo = _list_by_id(board, todo_list_id)
        c_id = _card_id_by_title(in_progress, "C")
        d_id = _card_id_by_title(todo, "D")
        await _move_card(
            client,
            headers,
            card_id=c_id,
            target_list_id=todo_list_id,
            prev_card_id=d_id,
            next_card_id=None,
        )
        board = await _fetch_board(client, headers, board_id)
        _assert_list_titles(board, todo_list_id, ["A", "B", "D", "C"])
        _assert_list_titles(board, in_progress_list_id, [])
        _assert_board_card_integrity(board)

        todo = _list_by_id(board, todo_list_id)
        c_id = _card_id_by_title(todo, "C")
        a_id = _card_id_by_title(todo, "A")
        await _move_card(
            client,
            headers,
            card_id=c_id,
            target_list_id=todo_list_id,
            prev_card_id=None,
            next_card_id=a_id,
        )
        board = await _fetch_board(client, headers, board_id)
        _assert_list_titles(board, todo_list_id, ["C", "A", "B", "D"])
        _assert_board_card_integrity(board)

        todo = _list_by_id(board, todo_list_id)
        a_id = _card_id_by_title(todo, "A")
        d_id = _card_id_by_title(todo, "D")
        await _move_card(
            client,
            headers,
            card_id=a_id,
            target_list_id=todo_list_id,
            prev_card_id=d_id,
            next_card_id=None,
        )
        board = await _fetch_board(client, headers, board_id)
        _assert_list_titles(board, todo_list_id, ["C", "B", "D", "A"])
        _assert_board_card_integrity(board)

        todo = _list_by_id(board, todo_list_id)
        c_id = _card_id_by_title(todo, "C")
        b_id = _card_id_by_title(todo, "B")
        d_id = _card_id_by_title(todo, "D")
        a_id = _card_id_by_title(todo, "A")
        await _move_card(
            client,
            headers,
            card_id=d_id,
            target_list_id=todo_list_id,
            prev_card_id=c_id,
            next_card_id=b_id,
        )
        board = await _fetch_board(client, headers, board_id)
        _assert_list_titles(board, todo_list_id, ["C", "D", "B", "A"])
        _assert_board_card_integrity(board)

        todo = _list_by_id(board, todo_list_id)
        d_id = _card_id_by_title(todo, "D")
        b_id = _card_id_by_title(todo, "B")
        a_id = _card_id_by_title(todo, "A")
        await _move_card(
            client,
            headers,
            card_id=a_id,
            target_list_id=todo_list_id,
            prev_card_id=d_id,
            next_card_id=b_id,
        )
        board = await _fetch_board(client, headers, board_id)
        _assert_list_titles(board, todo_list_id, ["C", "D", "A", "B"])
        _assert_board_card_integrity(board)
