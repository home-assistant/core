"""Tests for the todo integration."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock

import pytest
import voluptuous as vol

from homeassistant.components.todo import (
    DOMAIN,
    TodoItem,
    TodoItemStatus,
    TodoListEntity,
    TodoListEntityFeature,
)
from homeassistant.config_entries import ConfigEntry, ConfigEntryState, ConfigFlow
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
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

    async def async_unload_entry_init(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
    ) -> bool:
        await hass.config_entries.async_unload_platforms(config_entry, [Platform.TODO])
        return True

    mock_platform(hass, f"{TEST_DOMAIN}.config_flow")
    mock_integration(
        hass,
        MockModule(
            TEST_DOMAIN,
            async_setup_entry=async_setup_entry_init,
            async_unload_entry=async_unload_entry_init,
        ),
    )


async def create_mock_platform(
    hass: HomeAssistant,
    entities: list[TodoListEntity],
) -> MockConfigEntry:
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

    return config_entry


@pytest.fixture(name="test_entity")
def mock_test_entity() -> TodoListEntity:
    """Fixture that creates a test TodoList entity with mock service calls."""
    entity1 = TodoListEntity()
    entity1.entity_id = "todo.entity1"
    entity1._attr_supported_features = (
        TodoListEntityFeature.CREATE_TODO_ITEM
        | TodoListEntityFeature.UPDATE_TODO_ITEM
        | TodoListEntityFeature.DELETE_TODO_ITEM
        | TodoListEntityFeature.MOVE_TODO_ITEM
    )
    entity1._attr_todo_items = [
        TodoItem(summary="Item #1", uid="1", status=TodoItemStatus.NEEDS_ACTION),
        TodoItem(summary="Item #2", uid="2", status=TodoItemStatus.COMPLETED),
    ]
    entity1.async_create_todo_item = AsyncMock()
    entity1.async_update_todo_item = AsyncMock()
    entity1.async_delete_todo_items = AsyncMock()
    entity1.async_move_todo_item = AsyncMock()
    return entity1


async def test_unload_entry(
    hass: HomeAssistant,
    test_entity: TodoListEntity,
) -> None:
    """Test unloading a config entry with a todo entity."""

    config_entry = await create_mock_platform(hass, [test_entity])
    assert config_entry.state == ConfigEntryState.LOADED

    state = hass.states.get("todo.entity1")
    assert state

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state == ConfigEntryState.NOT_LOADED

    state = hass.states.get("todo.entity1")
    assert not state


async def test_list_todo_items(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    test_entity: TodoListEntity,
) -> None:
    """Test listing items in a To-do list."""

    await create_mock_platform(hass, [test_entity])

    state = hass.states.get("todo.entity1")
    assert state
    assert state.state == "1"
    assert state.attributes == {"supported_features": 15}

    client = await hass_ws_client(hass)
    await client.send_json(
        {"id": 1, "type": "todo/item/list", "entity_id": "todo.entity1"}
    )
    resp = await client.receive_json()
    assert resp.get("id") == 1
    assert resp.get("success")
    assert resp.get("result") == {
        "items": [
            {"summary": "Item #1", "uid": "1", "status": "needs_action"},
            {"summary": "Item #2", "uid": "2", "status": "completed"},
        ]
    }


async def test_unsupported_websocket(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test a To-do list that does not support features."""

    entity1 = TodoListEntity()
    entity1.entity_id = "todo.entity1"
    await create_mock_platform(hass, [entity1])

    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 1,
            "type": "todo/item/list",
            "entity_id": "todo.unknown",
        }
    )
    resp = await client.receive_json()
    assert resp.get("id") == 1
    assert resp.get("error", {}).get("code") == "not_found"


async def test_add_item_service(
    hass: HomeAssistant,
    test_entity: TodoListEntity,
) -> None:
    """Test adding an item in a To-do list."""

    await create_mock_platform(hass, [test_entity])

    await hass.services.async_call(
        DOMAIN,
        "add_item",
        {"item": "New item"},
        target={"entity_id": "todo.entity1"},
        blocking=True,
    )

    args = test_entity.async_create_todo_item.call_args
    assert args
    item = args.kwargs.get("item")
    assert item
    assert item.uid is None
    assert item.summary == "New item"
    assert item.status == TodoItemStatus.NEEDS_ACTION


async def test_add_item_service_raises(
    hass: HomeAssistant,
    test_entity: TodoListEntity,
) -> None:
    """Test adding an item in a To-do list that raises an error."""

    await create_mock_platform(hass, [test_entity])

    test_entity.async_create_todo_item.side_effect = HomeAssistantError("Ooops")
    with pytest.raises(HomeAssistantError, match="Ooops"):
        await hass.services.async_call(
            DOMAIN,
            "add_item",
            {"item": "New item"},
            target={"entity_id": "todo.entity1"},
            blocking=True,
        )


@pytest.mark.parametrize(
    ("item_data", "expected_error"),
    [
        ({}, "required key not provided"),
        ({"item": ""}, "length of value must be at least 1"),
    ],
)
async def test_add_item_service_invalid_input(
    hass: HomeAssistant,
    test_entity: TodoListEntity,
    item_data: dict[str, Any],
    expected_error: str,
) -> None:
    """Test invalid input to the add item service."""

    await create_mock_platform(hass, [test_entity])

    with pytest.raises(vol.Invalid, match=expected_error):
        await hass.services.async_call(
            DOMAIN,
            "add_item",
            item_data,
            target={"entity_id": "todo.entity1"},
            blocking=True,
        )


async def test_update_todo_item_service_by_id(
    hass: HomeAssistant,
    test_entity: TodoListEntity,
) -> None:
    """Test updating an item in a To-do list."""

    await create_mock_platform(hass, [test_entity])

    await hass.services.async_call(
        DOMAIN,
        "update_item",
        {"item": "1", "rename": "Updated item", "status": "completed"},
        target={"entity_id": "todo.entity1"},
        blocking=True,
    )

    args = test_entity.async_update_todo_item.call_args
    assert args
    item = args.kwargs.get("item")
    assert item
    assert item.uid == "1"
    assert item.summary == "Updated item"
    assert item.status == TodoItemStatus.COMPLETED


async def test_update_todo_item_service_by_id_status_only(
    hass: HomeAssistant,
    test_entity: TodoListEntity,
) -> None:
    """Test updating an item in a To-do list."""

    await create_mock_platform(hass, [test_entity])

    await hass.services.async_call(
        DOMAIN,
        "update_item",
        {"item": "1", "status": "completed"},
        target={"entity_id": "todo.entity1"},
        blocking=True,
    )

    args = test_entity.async_update_todo_item.call_args
    assert args
    item = args.kwargs.get("item")
    assert item
    assert item.uid == "1"
    assert item.summary is None
    assert item.status == TodoItemStatus.COMPLETED


async def test_update_todo_item_service_by_id_rename(
    hass: HomeAssistant,
    test_entity: TodoListEntity,
) -> None:
    """Test updating an item in a To-do list."""

    await create_mock_platform(hass, [test_entity])

    await hass.services.async_call(
        DOMAIN,
        "update_item",
        {"item": "1", "rename": "Updated item"},
        target={"entity_id": "todo.entity1"},
        blocking=True,
    )

    args = test_entity.async_update_todo_item.call_args
    assert args
    item = args.kwargs.get("item")
    assert item
    assert item.uid == "1"
    assert item.summary == "Updated item"
    assert item.status is None


async def test_update_todo_item_service_raises(
    hass: HomeAssistant,
    test_entity: TodoListEntity,
) -> None:
    """Test updating an item in a To-do list that raises an error."""

    await create_mock_platform(hass, [test_entity])

    await hass.services.async_call(
        DOMAIN,
        "update_item",
        {"item": "1", "rename": "Updated item", "status": "completed"},
        target={"entity_id": "todo.entity1"},
        blocking=True,
    )

    test_entity.async_update_todo_item.side_effect = HomeAssistantError("Ooops")
    with pytest.raises(HomeAssistantError, match="Ooops"):
        await hass.services.async_call(
            DOMAIN,
            "update_item",
            {"item": "1", "rename": "Updated item", "status": "completed"},
            target={"entity_id": "todo.entity1"},
            blocking=True,
        )


async def test_update_todo_item_service_by_summary(
    hass: HomeAssistant,
    test_entity: TodoListEntity,
) -> None:
    """Test updating an item in a To-do list by summary."""

    await create_mock_platform(hass, [test_entity])

    await hass.services.async_call(
        DOMAIN,
        "update_item",
        {"item": "Item #1", "rename": "Something else", "status": "completed"},
        target={"entity_id": "todo.entity1"},
        blocking=True,
    )

    args = test_entity.async_update_todo_item.call_args
    assert args
    item = args.kwargs.get("item")
    assert item
    assert item.uid == "1"
    assert item.summary == "Something else"
    assert item.status == TodoItemStatus.COMPLETED


async def test_update_todo_item_service_by_summary_only_status(
    hass: HomeAssistant,
    test_entity: TodoListEntity,
) -> None:
    """Test updating an item in a To-do list by summary."""

    await create_mock_platform(hass, [test_entity])

    await hass.services.async_call(
        DOMAIN,
        "update_item",
        {"item": "Item #1", "rename": "Something else"},
        target={"entity_id": "todo.entity1"},
        blocking=True,
    )

    args = test_entity.async_update_todo_item.call_args
    assert args
    item = args.kwargs.get("item")
    assert item
    assert item.uid == "1"
    assert item.summary == "Something else"
    assert item.status is None


async def test_update_todo_item_service_by_summary_not_found(
    hass: HomeAssistant,
    test_entity: TodoListEntity,
) -> None:
    """Test updating an item in a To-do list by summary which is not found."""

    await create_mock_platform(hass, [test_entity])

    with pytest.raises(ValueError, match="Unable to find"):
        await hass.services.async_call(
            DOMAIN,
            "update_item",
            {"item": "Item #7", "status": "completed"},
            target={"entity_id": "todo.entity1"},
            blocking=True,
        )


@pytest.mark.parametrize(
    ("item_data", "expected_error"),
    [
        ({}, r"required key not provided @ data\['item'\]"),
        ({"status": "needs_action"}, r"required key not provided @ data\['item'\]"),
        ({"item": "Item #1"}, "must contain at least one of"),
        (
            {"item": "", "status": "needs_action"},
            "length of value must be at least 1",
        ),
    ],
)
async def test_update_item_service_invalid_input(
    hass: HomeAssistant,
    test_entity: TodoListEntity,
    item_data: dict[str, Any],
    expected_error: str,
) -> None:
    """Test invalid input to the update item service."""

    await create_mock_platform(hass, [test_entity])

    with pytest.raises(vol.Invalid, match=expected_error):
        await hass.services.async_call(
            DOMAIN,
            "update_item",
            item_data,
            target={"entity_id": "todo.entity1"},
            blocking=True,
        )


async def test_remove_todo_item_service_by_id(
    hass: HomeAssistant,
    test_entity: TodoListEntity,
) -> None:
    """Test removing an item in a To-do list."""

    await create_mock_platform(hass, [test_entity])

    await hass.services.async_call(
        DOMAIN,
        "remove_item",
        {"item": ["1", "2"]},
        target={"entity_id": "todo.entity1"},
        blocking=True,
    )

    args = test_entity.async_delete_todo_items.call_args
    assert args
    assert args.kwargs.get("uids") == ["1", "2"]


async def test_remove_todo_item_service_raises(
    hass: HomeAssistant,
    test_entity: TodoListEntity,
) -> None:
    """Test removing an item in a To-do list that raises an error."""

    await create_mock_platform(hass, [test_entity])

    test_entity.async_delete_todo_items.side_effect = HomeAssistantError("Ooops")
    with pytest.raises(HomeAssistantError, match="Ooops"):
        await hass.services.async_call(
            DOMAIN,
            "remove_item",
            {"item": ["1", "2"]},
            target={"entity_id": "todo.entity1"},
            blocking=True,
        )


async def test_remove_todo_item_service_invalid_input(
    hass: HomeAssistant,
    test_entity: TodoListEntity,
) -> None:
    """Test invalid input to the remove item service."""

    await create_mock_platform(hass, [test_entity])

    with pytest.raises(
        vol.Invalid, match=r"required key not provided @ data\['item'\]"
    ):
        await hass.services.async_call(
            DOMAIN,
            "remove_item",
            {},
            target={"entity_id": "todo.entity1"},
            blocking=True,
        )


async def test_remove_todo_item_service_by_summary(
    hass: HomeAssistant,
    test_entity: TodoListEntity,
) -> None:
    """Test removing an item in a To-do list by summary."""

    await create_mock_platform(hass, [test_entity])

    await hass.services.async_call(
        DOMAIN,
        "remove_item",
        {"item": ["Item #1"]},
        target={"entity_id": "todo.entity1"},
        blocking=True,
    )

    args = test_entity.async_delete_todo_items.call_args
    assert args
    assert args.kwargs.get("uids") == ["1"]


async def test_remove_todo_item_service_by_summary_not_found(
    hass: HomeAssistant,
    test_entity: TodoListEntity,
) -> None:
    """Test removing an item in a To-do list by summary which is not found."""

    await create_mock_platform(hass, [test_entity])

    with pytest.raises(ValueError, match="Unable to find"):
        await hass.services.async_call(
            DOMAIN,
            "remove_item",
            {"item": ["Item #7"]},
            target={"entity_id": "todo.entity1"},
            blocking=True,
        )


async def test_move_todo_item_service_by_id(
    hass: HomeAssistant,
    test_entity: TodoListEntity,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test moving an item in a To-do list."""

    await create_mock_platform(hass, [test_entity])

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "todo/item/move",
            "entity_id": "todo.entity1",
            "uid": "item-1",
            "previous_uid": "item-2",
        }
    )
    resp = await client.receive_json()
    assert resp.get("id") == 1
    assert resp.get("success")

    args = test_entity.async_move_todo_item.call_args
    assert args
    assert args.kwargs.get("uid") == "item-1"
    assert args.kwargs.get("previous_uid") == "item-2"


async def test_move_todo_item_service_raises(
    hass: HomeAssistant,
    test_entity: TodoListEntity,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test moving an item in a To-do list that raises an error."""

    await create_mock_platform(hass, [test_entity])

    test_entity.async_move_todo_item.side_effect = HomeAssistantError("Ooops")
    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "todo/item/move",
            "entity_id": "todo.entity1",
            "uid": "item-1",
            "previous_uid": "item-2",
        }
    )
    resp = await client.receive_json()
    assert resp.get("id") == 1
    assert resp.get("error", {}).get("code") == "failed"
    assert resp.get("error", {}).get("message") == "Ooops"


@pytest.mark.parametrize(
    ("item_data", "expected_status", "expected_error"),
    [
        (
            {"entity_id": "todo.unknown", "uid": "item-1"},
            "not_found",
            "Entity not found",
        ),
        ({"entity_id": "todo.entity1"}, "invalid_format", "required key not provided"),
        (
            {"entity_id": "todo.entity1", "previous_uid": "item-2"},
            "invalid_format",
            "required key not provided",
        ),
    ],
)
async def test_move_todo_item_service_invalid_input(
    hass: HomeAssistant,
    test_entity: TodoListEntity,
    hass_ws_client: WebSocketGenerator,
    item_data: dict[str, Any],
    expected_status: str,
    expected_error: str,
) -> None:
    """Test invalid input for the move item service."""

    await create_mock_platform(hass, [test_entity])

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "todo/item/move",
            **item_data,
        }
    )
    resp = await client.receive_json()
    assert resp.get("id") == 1
    assert resp.get("error", {}).get("code") == expected_status
    assert expected_error in resp.get("error", {}).get("message")


@pytest.mark.parametrize(
    ("service_name", "payload"),
    [
        (
            "add_item",
            {
                "item": "New item",
            },
        ),
        (
            "remove_item",
            {
                "item": ["1"],
            },
        ),
        (
            "update_item",
            {
                "item": "1",
                "rename": "Updated item",
            },
        ),
    ],
)
async def test_unsupported_service(
    hass: HomeAssistant,
    service_name: str,
    payload: dict[str, Any],
) -> None:
    """Test a To-do list that does not support features."""

    entity1 = TodoListEntity()
    entity1.entity_id = "todo.entity1"
    await create_mock_platform(hass, [entity1])

    with pytest.raises(
        HomeAssistantError,
        match="does not support this service",
    ):
        await hass.services.async_call(
            DOMAIN,
            service_name,
            payload,
            target={"entity_id": "todo.entity1"},
            blocking=True,
        )


async def test_move_item_unsupported(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test invalid input for the move item service."""

    entity1 = TodoListEntity()
    entity1.entity_id = "todo.entity1"
    await create_mock_platform(hass, [entity1])

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "todo/item/move",
            "entity_id": "todo.entity1",
            "uid": "item-1",
            "previous_uid": "item-2",
        }
    )
    resp = await client.receive_json()
    assert resp.get("id") == 1
    assert resp.get("error", {}).get("code") == "not_supported"
