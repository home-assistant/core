"""Tests for AnyList todo entities."""

from operator import attrgetter
from unittest.mock import MagicMock

from aioanylist import AnyListError, Domain
from aioanylist.proto import PB
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.todo import (
    ATTR_DESCRIPTION,
    ATTR_ITEM,
    ATTR_RENAME,
    ATTR_STATUS,
    DOMAIN as TODO_DOMAIN,
    TodoServices,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .conftest import ITEM_ID, LIST_ID

ENTITY_ID = "todo.groceries"


async def test_todo_entity(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_anylist_client: MagicMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the AnyList shopping list entity."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == "1"
    assert state.name == "Groceries"

    entry = entity_registry.async_get(ENTITY_ID)
    assert entry is not None
    assert entry.unique_id == f"{mock_config_entry.unique_id}_{LIST_ID}"
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_add_item(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_anylist_client: MagicMock,
) -> None:
    """Test adding an AnyList item through the todo service."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.ADD_ITEM,
        {ATTR_ITEM: "Apples", ATTR_DESCRIPTION: "Honeycrisp"},
        target={ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    mock_anylist_client.lists.add_item.assert_awaited_once_with(
        LIST_ID,
        "Apples",
        details="Honeycrisp",
    )


async def test_update_item(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_anylist_client: MagicMock,
) -> None:
    """Test renaming, completing, and editing details on an AnyList item."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.UPDATE_ITEM,
        {
            ATTR_ITEM: ITEM_ID,
            ATTR_RENAME: "Oat milk",
            ATTR_STATUS: "completed",
            ATTR_DESCRIPTION: "Unsweetened",
        },
        target={ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    mock_anylist_client.lists.rename_item.assert_awaited_once_with(
        LIST_ID, ITEM_ID, "Oat milk", flush=False
    )
    mock_anylist_client.lists.set_checked.assert_awaited_once_with(
        LIST_ID, ITEM_ID, True, flush=False
    )
    mock_anylist_client.lists.set_details.assert_awaited_once_with(
        LIST_ID, ITEM_ID, "Unsweetened", flush=False
    )
    mock_anylist_client.flush.assert_awaited_once()


async def test_delete_items(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_anylist_client: MagicMock,
) -> None:
    """Test deleting AnyList items through the todo service."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.REMOVE_ITEM,
        {ATTR_ITEM: ITEM_ID},
        target={ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    mock_anylist_client.lists.bulk_remove_items.assert_awaited_once_with(
        LIST_ID, [ITEM_ID]
    )


@pytest.mark.parametrize(
    ("service", "data", "method", "translation_key"),
    [
        (
            TodoServices.ADD_ITEM,
            {ATTR_ITEM: "Apples"},
            "lists.add_item",
            "add_item_failed",
        ),
        (
            TodoServices.UPDATE_ITEM,
            {ATTR_ITEM: ITEM_ID, ATTR_RENAME: "Oat milk"},
            "flush",
            "update_item_failed",
        ),
        (
            TodoServices.REMOVE_ITEM,
            {ATTR_ITEM: ITEM_ID},
            "lists.bulk_remove_items",
            "delete_item_failed",
        ),
    ],
)
@pytest.mark.parametrize("error", [AnyListError(), TimeoutError()])
async def test_todo_action_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_anylist_client: MagicMock,
    service: str,
    data: dict[str, str],
    method: str,
    translation_key: str,
    error: Exception,
) -> None:
    """Test AnyList mutation errors are translated to Home Assistant errors."""
    await setup_integration(hass, mock_config_entry)
    attrgetter(method)(mock_anylist_client).side_effect = error

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            TODO_DOMAIN,
            service,
            data,
            target={ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )

    assert err.value.translation_domain == "any_list"
    assert err.value.translation_key == translation_key


async def test_stale_list_entity_removed_on_startup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_anylist_client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a list deleted while Home Assistant was offline is removed on startup."""
    mock_config_entry.add_to_hass(hass)
    stale_unique_id = f"{mock_config_entry.unique_id}_deleted-list"
    stale = entity_registry.async_get_or_create(
        TODO_DOMAIN,
        "any_list",
        stale_unique_id,
        config_entry=mock_config_entry,
        suggested_object_id="deleted_list",
    )
    assert entity_registry.async_get(stale.entity_id) is not None

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert (
        entity_registry.async_get_entity_id(TODO_DOMAIN, "any_list", stale_unique_id)
        is None
    )


async def test_realtime_update(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_anylist_client: MagicMock,
) -> None:
    """Test a realtime AnyList sync updates the todo entity without polling."""
    await setup_integration(hass, mock_config_entry)
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == "1"

    item = mock_anylist_client.state.get_item(LIST_ID, ITEM_ID)
    assert item is not None
    item.checked = True

    await mock_anylist_client.sync_listener({Domain.SHOPPING_LISTS})
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == "0"
    mock_anylist_client.refresh.assert_not_awaited()


async def test_dynamic_lists(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_anylist_client: MagicMock,
) -> None:
    """Test shopping lists added and removed remotely update entities dynamically."""
    await setup_integration(hass, mock_config_entry)

    second_list = PB.ShoppingList(identifier="list-2", name="Hardware")
    mock_anylist_client.state.shopping_lists["list-2"] = second_list
    await mock_anylist_client.sync_listener({Domain.SHOPPING_LISTS})
    await hass.async_block_till_done()
    assert hass.states.get("todo.hardware") is not None

    del mock_anylist_client.state.shopping_lists["list-2"]
    await mock_anylist_client.sync_listener({Domain.SHOPPING_LISTS})
    await hass.async_block_till_done()
    assert hass.states.get("todo.hardware") is None


async def test_list_rename(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_anylist_client: MagicMock,
) -> None:
    """Test a remotely renamed shopping list updates the entity name."""
    await setup_integration(hass, mock_config_entry)
    assert (state := hass.states.get(ENTITY_ID)) is not None
    assert state.name == "Groceries"

    mock_anylist_client.state.shopping_lists[LIST_ID].name = "Weekly shop"
    await mock_anylist_client.sync_listener({Domain.SHOPPING_LISTS})
    await hass.async_block_till_done()

    assert (state := hass.states.get(ENTITY_ID)) is not None
    assert state.name == "Weekly shop"
