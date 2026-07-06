"""Test Alexa Devices todo entities."""

from typing import Any
from unittest.mock import AsyncMock, patch

from aioamazondevices import CannotAuthenticate, CannotConnect
from aioamazondevices.exceptions import CannotRetrieveData
from aioamazondevices.structures import (
    AmazonListEvent,
    AmazonListEventType,
    AmazonListInfo,
    AmazonListItem,
    AmazonListItemStatus,
    AmazonListType,
)
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.alexa_devices.coordinator import SCAN_INTERVAL
from homeassistant.components.todo import (
    DOMAIN as TODO_DOMAIN,
    TodoItemStatus,
    TodoServices,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import slugify

from . import setup_integration
from .const import TEST_USERNAME

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

LIST_ENTITY_ID_PREFIX = f"{TODO_DOMAIN.lower()}.{slugify(TEST_USERNAME)}_"
MOCK_SHOPPING_LIST_ENTITY_ID = f"{LIST_ENTITY_ID_PREFIX}shopping_list"
MOCK_TODO_LIST_ENTITY_ID = f"{LIST_ENTITY_ID_PREFIX}to_do_list"
MOCK_CUSTOM_LIST_ENTITY_ID = f"{LIST_ENTITY_ID_PREFIX}concerts"

MOCK_SHOPPING_LIST = AmazonListInfo(
    id="shopping_list_id", name=None, list_type=AmazonListType.SHOP
)
MOCK_TODO_LIST = AmazonListInfo(
    id="todo_list_id", name=None, list_type=AmazonListType.TODO
)
MOCK_CUSTOM_LIST = AmazonListInfo(
    id="custom_list_id", name="Concerts", list_type=AmazonListType.CUSTOM
)


@pytest.fixture
def mock_todo_lists():
    """Mock todo lists."""
    return [
        MOCK_SHOPPING_LIST,
        MOCK_TODO_LIST,
        MOCK_CUSTOM_LIST,
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
        "custom_list_id": {
            "item_4": AmazonListItem(
                id="item_4",
                name="TWICE",
                status=AmazonListItemStatus.ACTIVE,
                version=1,
            ),
            "item_5": AmazonListItem(
                id="item_5",
                name="BTS",
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

    entity_id = MOCK_TODO_LIST_ENTITY_ID

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

    entity_id = MOCK_TODO_LIST_ENTITY_ID

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

    entity_id = MOCK_TODO_LIST_ENTITY_ID

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
    mock_amazon_devices_client.rename_todo_list_item.assert_not_called()

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
    mock_amazon_devices_client.set_todo_list_item_checked_status.assert_not_called()

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


@pytest.mark.parametrize(
    ("initial_lists", "updated_lists"),
    [
        ([MOCK_TODO_LIST], [MOCK_TODO_LIST, MOCK_CUSTOM_LIST]),  # Add a list
        ([MOCK_TODO_LIST, MOCK_CUSTOM_LIST], [MOCK_TODO_LIST]),  # Remove a list
        (
            [MOCK_TODO_LIST, MOCK_SHOPPING_LIST, MOCK_CUSTOM_LIST],
            [],
        ),  # Remove all lists
    ],
)
async def test_dynamic_entities(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    initial_lists: list[AmazonListInfo],
    updated_lists: list[AmazonListInfo],
) -> None:
    """Test entities are dynamically created and deleted."""

    def get_entity_id(alexa_list: AmazonListInfo) -> str:
        if alexa_list.list_type == AmazonListType.SHOP:
            return MOCK_SHOPPING_LIST_ENTITY_ID
        if alexa_list.list_type == AmazonListType.TODO:
            return MOCK_TODO_LIST_ENTITY_ID
        return MOCK_CUSTOM_LIST_ENTITY_ID

    # Start with the initial set of lists from the Amazon client.
    mock_amazon_devices_client.todo_lists = list(initial_lists)
    mock_amazon_devices_client.get_todo_list_items = AsyncMock(return_value={})

    await setup_integration(hass, mock_config_entry)

    initial_entity_ids = [get_entity_id(alexa_list) for alexa_list in initial_lists]
    updated_entity_ids = [get_entity_id(alexa_list) for alexa_list in updated_lists]

    # Confirm the initially expected entities exist.
    for entity_id in initial_entity_ids:
        assert hass.states.get(entity_id) is not None

    # Update the Amazon client to return the new list set.
    mock_amazon_devices_client.todo_lists = list(updated_lists)

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Confirm the entities in the updated set exist.
    for entity_id in updated_entity_ids:
        assert hass.states.get(entity_id) is not None

    # Confirm removed entities are no longer present.
    for entity_id in set(initial_entity_ids) - set(updated_entity_ids):
        assert hass.states.get(entity_id) is None


async def test_dynamic_add_list_and_add_item(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test adding a new list and then adding an item to it."""
    mock_amazon_devices_client.todo_lists = []
    mock_amazon_devices_client.get_todo_list_items = AsyncMock(return_value={})

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(MOCK_TODO_LIST_ENTITY_ID) is None

    mock_amazon_devices_client.todo_lists = [MOCK_TODO_LIST]

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Send CREATED event for new item in the newly created list (imitate Amazon server)
    new_item_id = "item_1"
    new_item = AmazonListItem(
        id=new_item_id,
        name="New Task",
        status=AmazonListItemStatus.ACTIVE,
        version=1,
    )
    created_event = AmazonListEvent(
        list_id=MOCK_TODO_LIST.id,
        item_id=new_item_id,
        type=AmazonListEventType.CREATED,
        items=new_item,
    )

    coordinator = mock_config_entry.runtime_data
    await coordinator.todo_event_handler(created_event)

    assert hass.states.get(MOCK_TODO_LIST_ENTITY_ID) is not None


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

    # Test DELETED
    deleted_event = AmazonListEvent(
        list_id=list_id,
        item_id=item_id,
        type=AmazonListEventType.DELETED,
        items=None,
    )
    await coordinator.todo_event_handler(deleted_event)
    assert item_id not in coordinator.todo_list_items[list_id]


@pytest.mark.parametrize(
    ("side_effect", "expected_state"),
    [
        pytest.param(
            CannotAuthenticate,
            ConfigEntryState.SETUP_ERROR,
            id="cannot_authenticate",
        ),
        pytest.param(
            CannotConnect,
            ConfigEntryState.SETUP_RETRY,
            id="cannot_connect",
        ),
        pytest.param(
            CannotRetrieveData,
            ConfigEntryState.SETUP_RETRY,
            id="cannot_retrieve_data",
        ),
    ],
)
async def test_sync_todo_list_items_error(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    side_effect: type[Exception],
    expected_state: ConfigEntryState,
) -> None:
    """Test setup fails when syncing todo list items raises an error."""
    mock_amazon_devices_client.get_todo_list_items.side_effect = side_effect
    mock_amazon_devices_client.todo_lists = [
        AmazonListInfo(id="shopping_list_id", name=None, list_type=AmazonListType.SHOP)
    ]

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is expected_state
