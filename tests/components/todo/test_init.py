"""Tests for the todo integration."""

from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.bootstrap import async_setup_component
from homeassistant.components.todo import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from tests.typing import WebSocketGenerator


@pytest.fixture(autouse=True)
async def setup_homeassistant(hass: HomeAssistant):
    """Set up the homeassistant integration."""
    await async_setup_component(hass, "homeassistant", {})


@pytest.fixture(autouse=True)
async def select_only() -> None:
    """Enable only the select platform."""
    with patch(
        "homeassistant.components.demo.COMPONENTS_WITH_CONFIG_ENTRY_DEMO_PLATFORM",
        [Platform.TODO],
    ):
        yield


async def test_list_todo_items(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test listing items in a To-do list."""

    await async_setup_component(hass, DOMAIN, {DOMAIN: {"platform": "demo"}})
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)
    await client.send_json(
        {"id": 1, "type": "todo/item/list", "entity_id": "todo.reminders"}
    )
    resp = await client.receive_json()
    assert resp.get("id") == 1
    assert resp.get("success")
    assert resp.get("result") == {
        "items": [
            {"summary": "Item #1", "uid": "1", "status": "NEEDS-ACTION"},
            {"summary": "Item #2", "uid": "2", "status": "COMPLETED"},
        ]
    }


@pytest.mark.parametrize(
    ("payload", "expected_error"),
    [
        (
            {
                "type": "todo/item/list",
                "entity_id": "todo.unknown",
            },
            "not_found",
        ),
        (
            {
                "type": "todo/item/create",
                "entity_id": "todo.reminders",
                "item": {"summary": "New item"},
            },
            "not_supported",
        ),
        (
            {
                "type": "todo/item/create",
                "entity_id": "todo.unknown",
                "item": {"summary": "New item"},
            },
            "not_found",
        ),
        (
            {
                "type": "todo/item/delete",
                "entity_id": "todo.reminders",
                "uids": ["1"],
            },
            "not_supported",
        ),
        (
            {
                "type": "todo/item/delete",
                "entity_id": "todo.unknown",
                "uids": ["1"],
            },
            "not_found",
        ),
        (
            {
                "type": "todo/item/update",
                "entity_id": "todo.reminders",
                "item": {"uid": "1", "summary": "Updated item"},
            },
            "not_supported",
        ),
        (
            {
                "type": "todo/item/update",
                "entity_id": "todo.unknown",
                "item": {"uid": "1", "summary": "Updated item"},
            },
            "not_found",
        ),
        (
            {
                "type": "todo/item/move",
                "entity_id": "todo.reminders",
                "uid": "12345",
                "previous": "54321",
            },
            "not_supported",
        ),
        (
            {
                "type": "todo/item/move",
                "entity_id": "todo.unknown",
                "uid": "1234",
            },
            "not_found",
        ),
    ],
)
async def test_unsupported(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    payload: dict[str, Any],
    expected_error: str,
) -> None:
    """Test a To-do list that does not support features."""
    await async_setup_component(hass, DOMAIN, {DOMAIN: {"platform": "demo"}})
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, **payload})
    resp = await client.receive_json()
    assert resp.get("id") == 1
    assert resp.get("error", {}).get("code") == expected_error
