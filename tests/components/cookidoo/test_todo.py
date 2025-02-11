"""Test for todo platform of the Cookidoo integration."""

from collections.abc import Generator
import re
from unittest.mock import AsyncMock, patch

from cookidoo_api import (
    CookidooAdditionalItem,
    CookidooIngredientItem,
    CookidooRequestException,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.todo import (
    ATTR_ITEM,
    ATTR_RENAME,
    ATTR_STATUS,
    DOMAIN as TODO_DOMAIN,
    TodoItemStatus,
    TodoServices,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture(autouse=True)
def todo_only() -> Generator[None]:
    """Enable only the todo platform."""
    with patch(
        "homeassistant.components.cookidoo.PLATFORMS",
        [Platform.TODO],
    ):
        yield


@pytest.mark.usefixtures("mock_cookidoo_client")
async def test_todo(
    hass: HomeAssistant,
    cookidoo_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Snapshot test states of todo platform."""

    with patch("homeassistant.components.cookidoo.PLATFORMS", [Platform.TODO]):
        await setup_integration(hass, cookidoo_config_entry)

    assert cookidoo_config_entry.state is ConfigEntryState.LOADED

    await snapshot_platform(
        hass, entity_registry, snapshot, cookidoo_config_entry.entry_id
    )


async def test_update_ingredient(
    hass: HomeAssistant,
    cookidoo_config_entry: MockConfigEntry,
    mock_cookidoo_client: AsyncMock,
) -> None:
    """Test update ingredient item."""

    await setup_integration(hass, cookidoo_config_entry)

    assert cookidoo_config_entry.state is ConfigEntryState.LOADED

    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.UPDATE_ITEM,
        service_data={
            ATTR_ITEM: "unique_id_mehl",
            ATTR_STATUS: TodoItemStatus.COMPLETED,
        },
        target={ATTR_ENTITY_ID: "todo.cookidoo_shopping_list"},
        blocking=True,
    )

    mock_cookidoo_client.edit_ingredient_items_ownership.assert_called_once_with(
        [
            CookidooIngredientItem(
                id="unique_id_mehl",
                name="",
                description="",
                is_owned=True,
            )
        ],
    )


async def test_update_ingredient_exception(
    hass: HomeAssistant,
    cookidoo_config_entry: MockConfigEntry,
    mock_cookidoo_client: AsyncMock,
) -> None:
    """Test update ingredient with exception."""

    await setup_integration(hass, cookidoo_config_entry)

    assert cookidoo_config_entry.state is ConfigEntryState.LOADED

    mock_cookidoo_client.edit_ingredient_items_ownership.side_effect = (
        CookidooRequestException
    )
    with pytest.raises(
        HomeAssistantError, match="Failed to update Mehl in Cookidoo shopping list"
    ):
        await hass.services.async_call(
            TODO_DOMAIN,
            TodoServices.UPDATE_ITEM,
            service_data={
                ATTR_ITEM: "unique_id_mehl",
                ATTR_STATUS: TodoItemStatus.COMPLETED,
            },
            target={ATTR_ENTITY_ID: "todo.cookidoo_shopping_list"},
            blocking=True,
        )


async def test_add_additional_item(
    hass: HomeAssistant,
    cookidoo_config_entry: MockConfigEntry,
    mock_cookidoo_client: AsyncMock,
) -> None:
    """Test add additional item to list."""

    await setup_integration(hass, cookidoo_config_entry)

    assert cookidoo_config_entry.state is ConfigEntryState.LOADED

    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.ADD_ITEM,
        service_data={ATTR_ITEM: "Äpfel"},
        target={ATTR_ENTITY_ID: "todo.cookidoo_additional_purchases"},
        blocking=True,
    )

    mock_cookidoo_client.add_additional_items.assert_called_once_with(
        ["Äpfel"],
    )


async def test_add_additional_item_exception(
    hass: HomeAssistant,
    cookidoo_config_entry: MockConfigEntry,
    mock_cookidoo_client: AsyncMock,
) -> None:
    """Test add additional item to list with exception."""

    await setup_integration(hass, cookidoo_config_entry)

    assert cookidoo_config_entry.state is ConfigEntryState.LOADED

    mock_cookidoo_client.add_additional_items.side_effect = CookidooRequestException
    with pytest.raises(
        HomeAssistantError, match="Failed to save Äpfel to Cookidoo shopping list"
    ):
        await hass.services.async_call(
            TODO_DOMAIN,
            TodoServices.ADD_ITEM,
            service_data={ATTR_ITEM: "Äpfel"},
            target={ATTR_ENTITY_ID: "todo.cookidoo_additional_purchases"},
            blocking=True,
        )


async def test_update_additional_item(
    hass: HomeAssistant,
    cookidoo_config_entry: MockConfigEntry,
    mock_cookidoo_client: AsyncMock,
) -> None:
    """Test update additional item."""

    await setup_integration(hass, cookidoo_config_entry)

    assert cookidoo_config_entry.state is ConfigEntryState.LOADED

    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.UPDATE_ITEM,
        service_data={
            ATTR_ITEM: "unique_id_tomaten",
            ATTR_RENAME: "Peperoni",
            ATTR_STATUS: TodoItemStatus.COMPLETED,
        },
        target={ATTR_ENTITY_ID: "todo.cookidoo_additional_purchases"},
        blocking=True,
    )

    mock_cookidoo_client.edit_additional_items_ownership.assert_called_once_with(
        [
            CookidooAdditionalItem(
                id="unique_id_tomaten",
                name="Peperoni",
                is_owned=True,
            )
        ],
    )
    mock_cookidoo_client.edit_additional_items.assert_called_once_with(
        [
            CookidooAdditionalItem(
                id="unique_id_tomaten",
                name="Peperoni",
                is_owned=True,
            )
        ],
    )


async def test_update_additional_item_exception(
    hass: HomeAssistant,
    cookidoo_config_entry: MockConfigEntry,
    mock_cookidoo_client: AsyncMock,
) -> None:
    """Test update additional item with exception."""

    await setup_integration(hass, cookidoo_config_entry)

    assert cookidoo_config_entry.state is ConfigEntryState.LOADED

    mock_cookidoo_client.edit_additional_items_ownership.side_effect = (
        CookidooRequestException
    )
    mock_cookidoo_client.edit_additional_items.side_effect = CookidooRequestException
    with pytest.raises(
        HomeAssistantError, match="Failed to update Peperoni in Cookidoo shopping list"
    ):
        await hass.services.async_call(
            TODO_DOMAIN,
            TodoServices.UPDATE_ITEM,
            service_data={
                ATTR_ITEM: "unique_id_tomaten",
                ATTR_RENAME: "Peperoni",
                ATTR_STATUS: TodoItemStatus.COMPLETED,
            },
            target={ATTR_ENTITY_ID: "todo.cookidoo_additional_purchases"},
            blocking=True,
        )


async def test_delete_additional_items(
    hass: HomeAssistant,
    cookidoo_config_entry: MockConfigEntry,
    mock_cookidoo_client: AsyncMock,
) -> None:
    """Test delete additional item."""

    await setup_integration(hass, cookidoo_config_entry)

    assert cookidoo_config_entry.state is ConfigEntryState.LOADED

    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.REMOVE_ITEM,
        service_data={ATTR_ITEM: "unique_id_tomaten"},
        target={ATTR_ENTITY_ID: "todo.cookidoo_additional_purchases"},
        blocking=True,
    )

    mock_cookidoo_client.remove_additional_items.assert_called_once_with(
        ["unique_id_tomaten"]
    )


async def test_delete_additional_items_exception(
    hass: HomeAssistant,
    cookidoo_config_entry: MockConfigEntry,
    mock_cookidoo_client: AsyncMock,
) -> None:
    """Test delete additional item."""

    await setup_integration(hass, cookidoo_config_entry)

    assert cookidoo_config_entry.state is ConfigEntryState.LOADED
    mock_cookidoo_client.remove_additional_items.side_effect = CookidooRequestException
    with pytest.raises(
        HomeAssistantError,
        match=re.escape("Failed to delete 1 item(s) from Cookidoo shopping list"),
    ):
        await hass.services.async_call(
            TODO_DOMAIN,
            TodoServices.REMOVE_ITEM,
            service_data={ATTR_ITEM: "unique_id_tomaten"},
            target={ATTR_ENTITY_ID: "todo.cookidoo_additional_purchases"},
            blocking=True,
        )
