"""Test Alexa Devices todo entities."""

from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

from aioamazondevices.structures import (
    AmazonListEvent,
    AmazonListEventType,
    AmazonListInfo,
    AmazonListItem,
    AmazonListItemStatus,
    AmazonListType,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.alexa_devices.todo import AlexaToDoList
from homeassistant.components.todo import (
    DATA_COMPONENT,
    DOMAIN as TODO_DOMAIN,
    TodoItem,
    TodoItemStatus,
    TodoServices,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.util import slugify

from . import setup_integration
from .const import TEST_USERNAME

from tests.common import MockConfigEntry, snapshot_platform

ENTITY_ID_PREFIX = f"todo.{slugify(TEST_USERNAME)}"


@pytest.fixture
def mock_todo_lists():
    """Mock todo lists."""
    return [
        AmazonListInfo(id="shopping_list_id", name=None, list_type=AmazonListType.SHOP),
        AmazonListInfo(id="todo_list_id", name=None, list_type=AmazonListType.TODO),
    ]


@pytest.fixture
def mock_todo_items():
    """Mock todo items."""
    return {
        "shopping_list_id": {
            "item_1": AmazonListItem(
                id="item_1",
                name="Bubble tea",
                status=AmazonListItemStatus.ACTIVE,
                version=1,
            ),
        },
        "todo_list_id": {
            "item_2": AmazonListItem(
                id="item_2",
                name="Task 1",
                status=AmazonListItemStatus.ACTIVE,
                version=1,
            ),
            "item_3": AmazonListItem(
                id="item_3",
                name="Task 2",
                status=AmazonListItemStatus.COMPLETE,
                version=2,
            ),
        },
    }


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_todo_lists: list[AmazonListInfo],
    mock_todo_items: dict[str, Any],
) -> None:
    """Test all entities."""
    mock_amazon_devices_client.todo_lists = mock_todo_lists
    mock_amazon_devices_client.get_todo_list_items = AsyncMock(
        side_effect=lambda list_id: mock_todo_items.get(list_id, {})
    )

    with patch("homeassistant.components.alexa_devices.PLATFORMS", [Platform.TODO]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_add_todo_item(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_todo_lists: list[AmazonListInfo],
) -> None:
    """Test adding a todo item."""
    mock_amazon_devices_client.todo_lists = mock_todo_lists
    mock_amazon_devices_client.get_todo_list_items = AsyncMock(return_value={})

    await setup_integration(hass, mock_config_entry)

    entity_id = f"{ENTITY_ID_PREFIX}_to_do_list"

    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.ADD_ITEM,
        {ATTR_ENTITY_ID: entity_id, "item": "New Task"},
        blocking=True,
    )

    mock_amazon_devices_client.add_todo_list_item.assert_called_once_with(
        "todo_list_id", "New Task"
    )


async def test_delete_todo_item(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_todo_lists: list[AmazonListInfo],
    mock_todo_items: dict[str, Any],
) -> None:
    """Test deleting a todo item."""
    mock_amazon_devices_client.todo_lists = mock_todo_lists
    mock_amazon_devices_client.get_todo_list_items = AsyncMock(
        side_effect=lambda list_id: mock_todo_items.get(list_id, {})
    )

    await setup_integration(hass, mock_config_entry)

    entity_id = f"{ENTITY_ID_PREFIX}_to_do_list"

    # Delete item_2
    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.REMOVE_ITEM,
        {ATTR_ENTITY_ID: entity_id, "item": ["item_2"]},
        blocking=True,
    )

    mock_amazon_devices_client.delete_todo_list_item.assert_called_once_with(
        "todo_list_id", "item_2", 1
    )


async def test_update_todo_item(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_todo_lists: list[AmazonListInfo],
    mock_todo_items: dict[str, Any],
) -> None:
    """Test updating a todo item."""
    mock_amazon_devices_client.todo_lists = mock_todo_lists
    mock_amazon_devices_client.get_todo_list_items = AsyncMock(
        side_effect=lambda list_id: mock_todo_items.get(list_id, {})
    )

    await setup_integration(hass, mock_config_entry)

    entity_id = f"{ENTITY_ID_PREFIX}_to_do_list"

    # Update item_2 (ACTIVE -> COMPLETE)
    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.UPDATE_ITEM,
        {
            ATTR_ENTITY_ID: entity_id,
            "item": "item_2",
            "status": TodoItemStatus.COMPLETED,
        },
        blocking=True,
    )

    mock_amazon_devices_client.set_todo_list_item_checked_status.assert_called_once_with(
        "todo_list_id", "item_2", True, 1
    )

    # Rename item_2
    mock_amazon_devices_client.set_todo_list_item_checked_status.reset_mock()
    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.UPDATE_ITEM,
        {
            ATTR_ENTITY_ID: entity_id,
            "item": "item_2",
            "rename": "Renamed Task",
        },
        blocking=True,
    )

    mock_amazon_devices_client.rename_todo_list_item.assert_called_once_with(
        "todo_list_id", "item_2", "Renamed Task", 1
    )

    # Both status and rename changed
    mock_amazon_devices_client.set_todo_list_item_checked_status.reset_mock()
    mock_amazon_devices_client.rename_todo_list_item.reset_mock()
    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.UPDATE_ITEM,
        {
            ATTR_ENTITY_ID: entity_id,
            "item": "item_2",
            "rename": "Both Changed",
            "status": TodoItemStatus.COMPLETED,
        },
        blocking=True,
    )
    mock_amazon_devices_client.set_todo_list_item_checked_status.assert_called_once_with(
        "todo_list_id", "item_2", True, 1
    )
    mock_amazon_devices_client.rename_todo_list_item.assert_called_once_with(
        "todo_list_id", "item_2", "Both Changed", 2
    )


async def test_update_todo_item_errors(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_todo_lists: list[AmazonListInfo],
    mock_todo_items: dict[str, Any],
) -> None:
    """Test updating a todo item with errors."""
    mock_amazon_devices_client.todo_lists = mock_todo_lists
    mock_amazon_devices_client.get_todo_list_items = AsyncMock(
        side_effect=lambda list_id: mock_todo_items.get(list_id, {})
    )

    await setup_integration(hass, mock_config_entry)

    entity_id = f"{ENTITY_ID_PREFIX}_to_do_list"

    # Item not found in HA
    with pytest.raises(ServiceValidationError, match="Unable to find to-do list item"):
        await hass.services.async_call(
            TODO_DOMAIN,
            TodoServices.UPDATE_ITEM,
            {
                ATTR_ENTITY_ID: entity_id,
                "item": "non_existent_item",
                "status": TodoItemStatus.COMPLETED,
            },
            blocking=True,
        )

    # Test platform method directly for error paths that are harder to reach via service calls
    # Get the actual entity object from the component
    component = hass.data[DATA_COMPONENT]
    alexa_entity = cast(AlexaToDoList, component.get_entity(entity_id))
    assert alexa_entity is not None

    # Item not found in coordinator lookup
    with pytest.raises(ServiceValidationError, match="the item was not found"):
        await alexa_entity.async_update_todo_item(
            TodoItem(uid="non_existent", summary="Task")
        )

    # Item summary empty
    with pytest.raises(ServiceValidationError, match="Item summary cannot be empty"):
        await alexa_entity.async_create_todo_item(TodoItem(summary=""))

    # Item summary and UID required for update
    with pytest.raises(
        ServiceValidationError, match="Item summary and UID are required"
    ):
        await alexa_entity.async_update_todo_item(TodoItem(uid=None, summary="Task"))
    with pytest.raises(
        ServiceValidationError, match="Item summary and UID are required"
    ):
        await alexa_entity.async_update_todo_item(TodoItem(uid="item_1", summary=None))

    # Item not found for delete
    with pytest.raises(ServiceValidationError, match="the item was not found"):
        await alexa_entity.async_delete_todo_items(["non_existent"])

    # Lookup not found
    alexa_entity.coordinator._todo_list_items.pop(alexa_entity._list.id, None)
    with pytest.raises(
        ServiceValidationError, match="the cached list items could not be found"
    ):
        await alexa_entity.async_update_todo_item(
            TodoItem(uid="item_1", summary="Task")
        )
    with pytest.raises(
        ServiceValidationError, match="the cached list items could not be found"
    ):
        await alexa_entity.async_delete_todo_items(["item_1"])


async def test_dynamic_lists(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test entities are dynamically created."""
    mock_amazon_devices_client.todo_lists = [
        AmazonListInfo(
            id="shopping_list_id",
            name="Alexa Shopping List",
            list_type=AmazonListType.SHOP,
        ),
    ]
    mock_amazon_devices_client.get_todo_list_items = AsyncMock(return_value={})

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(f"{ENTITY_ID_PREFIX}_shopping_list") is not None
    assert hass.states.get(f"{ENTITY_ID_PREFIX}_to_do_list") is None

    # Add a new list
    mock_amazon_devices_client.todo_lists.append(
        AmazonListInfo(
            id="concert_list_id",
            name="Concerts",
            list_type=AmazonListType.CUSTOM,
        )
    )

    # Trigger update
    coordinator = mock_config_entry.runtime_data
    coordinator.async_update_listeners()
    await hass.async_block_till_done()

    assert hass.states.get(f"{ENTITY_ID_PREFIX}_shopping_list") is not None
    assert hass.states.get(f"{ENTITY_ID_PREFIX}_concerts") is not None


async def test_todo_event_handler(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_todo_lists: list[AmazonListInfo],
) -> None:
    """Test todo event handler."""
    mock_amazon_devices_client.todo_lists = mock_todo_lists
    mock_amazon_devices_client.get_todo_list_items = AsyncMock(return_value={})

    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data

    # Seed _todo_list_items
    list_id = "todo_list_id"
    item_id = "item_1"
    item = AmazonListItem(
        id=item_id,
        name="Original Task",
        status=AmazonListItemStatus.ACTIVE,
        version=1,
    )
    coordinator.todo_list_items[list_id] = {item_id: item}

    # Add a listener to check if data is updated
    listener = MagicMock()
    coordinator.async_add_listener(listener)

    # Test CREATED
    new_item_id = "item_2"
    new_item = AmazonListItem(
        id=new_item_id,
        name="New Task",
        status=AmazonListItemStatus.ACTIVE,
        version=1,
    )
    created_event = AmazonListEvent(
        list_id=list_id,
        item_id=new_item_id,
        type=AmazonListEventType.CREATED,
        items=new_item,
    )
    await coordinator.todo_event_handler(created_event)
    assert coordinator.todo_list_items[list_id][new_item_id] == new_item
    listener.assert_called_once()
    listener.reset_mock()

    # Test UPDATED
    updated_item = AmazonListItem(
        id=item_id,
        name="Updated Task",
        status=AmazonListItemStatus.COMPLETE,
        version=2,
    )
    updated_event = AmazonListEvent(
        list_id=list_id,
        item_id=item_id,
        type=AmazonListEventType.UPDATED,
        items=updated_item,
    )
    await coordinator.todo_event_handler(updated_event)
    assert coordinator.todo_list_items[list_id][item_id] == updated_item
    listener.assert_called_once()
    listener.reset_mock()

    # Test DELETED
    deleted_event = AmazonListEvent(
        list_id=list_id,
        item_id=item_id,
        type=AmazonListEventType.DELETED,
        items=None,
    )
    await coordinator.todo_event_handler(deleted_event)
    assert item_id not in coordinator.todo_list_items[list_id]
    listener.assert_called_once()
    listener.reset_mock()

    # Test event for unknown list (should log warning and return)
    unknown_event = AmazonListEvent(
        list_id="unknown_list",
        item_id="some_id",
        type=AmazonListEventType.CREATED,
        items=None,
    )
    await coordinator.todo_event_handler(unknown_event)
    listener.assert_not_called()
