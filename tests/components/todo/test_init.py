"""Tests for the todo integration."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock

import pytest

from homeassistant.components.todo import (
    DOMAIN,
    TodoItem,
    TodoItemStatus,
    TodoListEntity,
    TodoListEntityFeature,
)
from homeassistant.config_entries import ConfigEntry, ConfigFlow
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from tests.common import (
    MockConfigEntry,
    MockModule,
    MockPlatform,
    mock_config_flow,
    mock_integration,
    mock_platform,
)
from tests.typing import WebSocketGenerator

TEST_DOMAIN = "test"


class MockFlow(ConfigFlow):
    """Test flow."""


@pytest.fixture(autouse=True)
def config_flow_fixture(hass: HomeAssistant) -> Generator[None, None, None]:
    """Mock config flow."""
    mock_platform(hass, f"{TEST_DOMAIN}.config_flow")

    with mock_config_flow(TEST_DOMAIN, MockFlow):
        yield


@pytest.fixture(autouse=True)
def mock_setup_integration(hass: HomeAssistant) -> None:
    """Fixture to set up a mock integration."""

    async def async_setup_entry_init(
        hass: HomeAssistant, config_entry: ConfigEntry
    ) -> bool:
        """Set up test config entry."""
        await hass.config_entries.async_forward_entry_setup(config_entry, DOMAIN)
        return True

    mock_platform(hass, f"{TEST_DOMAIN}.config_flow")
    mock_integration(
        hass,
        MockModule(
            TEST_DOMAIN,
            async_setup_entry=async_setup_entry_init,
        ),
    )


async def create_mock_platform(
    hass: HomeAssistant, entities: list[TodoListEntity]
) -> None:
    """Create a todo platform with the specified entities."""

    async def async_setup_entry_platform(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
    ) -> None:
        """Set up test event platform via config entry."""
        async_add_entities(entities)

    mock_platform(
        hass,
        f"{TEST_DOMAIN}.{DOMAIN}",
        MockPlatform(async_setup_entry=async_setup_entry_platform),
    )

    config_entry = MockConfigEntry(domain=TEST_DOMAIN)
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


async def test_list_todo_items(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test listing items in a To-do list."""

    entity1 = TodoListEntity()
    entity1.entity_id = "todo.entity1"
    entity1._attr_todo_items = [
        TodoItem(summary="Item #1", uid="1", status=TodoItemStatus.NEEDS_ACTION),
        TodoItem(summary="Item #2", uid="2", status=TodoItemStatus.COMPLETED),
    ]
    await create_mock_platform(hass, [entity1])

    state = hass.states.get("todo.entity1")
    assert state
    assert state.state == "1"
    assert state.attributes == {}

    client = await hass_ws_client(hass)
    await client.send_json(
        {"id": 1, "type": "todo/item/list", "entity_id": "todo.entity1"}
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


async def test_create_todo_item(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test creating an item in a To-do list."""

    entity1 = TodoListEntity()
    entity1.entity_id = "todo.entity1"
    entity1._attr_supported_features = TodoListEntityFeature.CREATE_TODO_ITEM
    entity1.async_create_todo_item = AsyncMock()
    await create_mock_platform(hass, [entity1])

    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 1,
            "type": "todo/item/create",
            "entity_id": "todo.entity1",
            "item": {"summary": "New item"},
        }
    )
    resp = await client.receive_json()
    assert resp.get("id") == 1
    assert resp.get("success")

    args = entity1.async_create_todo_item.call_args
    assert args
    item = args.kwargs.get("item")
    assert item
    assert item.uid is None
    assert item.summary == "New item"
    assert item.status == TodoItemStatus.NEEDS_ACTION


async def test_update_todo_item(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test updationg an item in a To-do list."""

    entity1 = TodoListEntity()
    entity1.entity_id = "todo.entity1"
    entity1._attr_supported_features = TodoListEntityFeature.UPDATE_TODO_ITEM
    entity1.async_update_todo_item = AsyncMock()
    await create_mock_platform(hass, [entity1])

    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 1,
            "type": "todo/item/update",
            "entity_id": "todo.entity1",
            "item": {"uid": "item-1", "summary": "Updated item", "status": "COMPLETED"},
        }
    )
    resp = await client.receive_json()
    assert resp.get("id") == 1
    assert resp.get("success")

    args = entity1.async_update_todo_item.call_args
    assert args
    item = args.kwargs.get("item")
    assert item
    assert item.uid == "item-1"
    assert item.summary == "Updated item"
    assert item.status == TodoItemStatus.COMPLETED


async def test_delete_todo_item(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test deleting an item in a To-do list."""

    entity1 = TodoListEntity()
    entity1.entity_id = "todo.entity1"
    entity1._attr_supported_features = TodoListEntityFeature.DELETE_TODO_ITEM
    entity1.async_delete_todo_items = AsyncMock()
    await create_mock_platform(hass, [entity1])

    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 1,
            "type": "todo/item/delete",
            "entity_id": "todo.entity1",
            "uids": ["item-1", "item-2"],
        }
    )
    resp = await client.receive_json()
    assert resp.get("id") == 1
    assert resp.get("success")

    args = entity1.async_delete_todo_items.call_args
    assert args
    assert args.kwargs.get("uids") == set({"item-1", "item-2"})


async def test_move_todo_item(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test moving an item in a To-do list."""

    entity1 = TodoListEntity()
    entity1.entity_id = "todo.entity1"
    entity1._attr_supported_features = TodoListEntityFeature.MOVE_TODO_ITEM
    entity1.async_move_todo_item = AsyncMock()
    await create_mock_platform(hass, [entity1])

    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 1,
            "type": "todo/item/move",
            "entity_id": "todo.entity1",
            "uid": "item-1",
            "previous": "item-2",
        }
    )
    resp = await client.receive_json()
    assert resp.get("id") == 1
    assert resp.get("success")

    args = entity1.async_move_todo_item.call_args
    assert args
    assert args.kwargs.get("uid") == "item-1"
    assert args.kwargs.get("previous") == "item-2"


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
                "entity_id": "todo.entity1",
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
                "entity_id": "todo.entity1",
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
                "entity_id": "todo.entity1",
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
                "entity_id": "todo.entity1",
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

    entity1 = TodoListEntity()
    entity1.entity_id = "todo.entity1"
    await create_mock_platform(hass, [entity1])

    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, **payload})
    resp = await client.receive_json()
    assert resp.get("id") == 1
    assert resp.get("error", {}).get("code") == expected_error
