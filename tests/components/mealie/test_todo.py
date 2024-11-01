"""Tests for the Mealie todo."""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

from aiomealie import MealieError, ShoppingListsResponse
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.mealie import DOMAIN
from homeassistant.components.todo import (
    ATTR_ITEM,
    ATTR_RENAME,
    ATTR_STATUS,
    DOMAIN as TODO_DOMAIN,
    TodoServices,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    load_fixture,
    snapshot_platform,
)


async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_mealie_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test todo entities."""
    with patch("homeassistant.components.mealie.PLATFORMS", [Platform.TODO]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_add_todo_list_item(
    hass: HomeAssistant,
    mock_mealie_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test for adding a To-do Item."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.ADD_ITEM,
        {ATTR_ITEM: "Soda"},
        target={ATTR_ENTITY_ID: "todo.mealie_supermarket"},
        blocking=True,
    )

    mock_mealie_client.add_shopping_item.assert_called_once()


async def test_add_todo_list_item_error(
    hass: HomeAssistant,
    mock_mealie_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test for failing to add a To-do Item."""
    await setup_integration(hass, mock_config_entry)

    mock_mealie_client.add_shopping_item.side_effect = MealieError

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            TODO_DOMAIN,
            TodoServices.ADD_ITEM,
            {ATTR_ITEM: "Soda"},
            target={ATTR_ENTITY_ID: "todo.mealie_supermarket"},
            blocking=True,
        )


async def test_update_todo_list_item(
    hass: HomeAssistant,
    mock_mealie_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test for updating a To-do Item."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.UPDATE_ITEM,
        {ATTR_ITEM: "aubergine", ATTR_RENAME: "Eggplant", ATTR_STATUS: "completed"},
        target={ATTR_ENTITY_ID: "todo.mealie_supermarket"},
        blocking=True,
    )

    mock_mealie_client.update_shopping_item.assert_called_once()


async def test_update_todo_list_item_error(
    hass: HomeAssistant,
    mock_mealie_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test for failing to update a To-do Item."""
    await setup_integration(hass, mock_config_entry)

    mock_mealie_client.update_shopping_item.side_effect = MealieError

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            TODO_DOMAIN,
            TodoServices.UPDATE_ITEM,
            {ATTR_ITEM: "aubergine", ATTR_RENAME: "Eggplant", ATTR_STATUS: "completed"},
            target={ATTR_ENTITY_ID: "todo.mealie_supermarket"},
            blocking=True,
        )


async def test_delete_todo_list_item(
    hass: HomeAssistant,
    mock_mealie_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test for deleting a To-do Item."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.REMOVE_ITEM,
        {ATTR_ITEM: "aubergine"},
        target={ATTR_ENTITY_ID: "todo.mealie_supermarket"},
        blocking=True,
    )

    mock_mealie_client.delete_shopping_item.assert_called_once()


async def test_delete_todo_list_item_error(
    hass: HomeAssistant,
    mock_mealie_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test for failing to delete a To-do Item."""
    await setup_integration(hass, mock_config_entry)

    mock_mealie_client.delete_shopping_item = AsyncMock()
    mock_mealie_client.delete_shopping_item.side_effect = MealieError

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            TODO_DOMAIN,
            TodoServices.REMOVE_ITEM,
            {ATTR_ITEM: "aubergine"},
            target={ATTR_ENTITY_ID: "todo.mealie_supermarket"},
            blocking=True,
        )


async def test_runtime_management(
    hass: HomeAssistant,
    mock_mealie_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test for creating and deleting shopping lists."""
    response = ShoppingListsResponse.from_json(
        load_fixture("get_shopping_lists.json", DOMAIN)
    ).items
    mock_mealie_client.get_shopping_lists.return_value = ShoppingListsResponse(
        items=[response[0]]
    )
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get("todo.mealie_supermarket") is not None
    assert hass.states.get("todo.mealie_special_groceries") is None

    mock_mealie_client.get_shopping_lists.return_value = ShoppingListsResponse(
        items=response[0:2]
    )
    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("todo.mealie_special_groceries") is not None

    mock_mealie_client.get_shopping_lists.return_value = ShoppingListsResponse(
        items=[response[0]]
    )
    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("todo.mealie_special_groceries") is None
