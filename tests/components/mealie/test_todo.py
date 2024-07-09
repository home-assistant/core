"""Tests for the Mealie todo."""

from unittest.mock import AsyncMock, patch

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.todo import DOMAIN as TODO_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


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


async def test_get_todo_list_items(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_mealie_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test for getting a To-do list."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("todo.mealie_supermarket")
    assert state
    assert state == snapshot


async def test_add_todo_list_item(
    hass: HomeAssistant,
    mock_mealie_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test for adding a To-do Item."""
    await setup_integration(hass, mock_config_entry)

    mock_mealie_client.add_shopping_item = AsyncMock()

    await hass.services.async_call(
        TODO_DOMAIN,
        "add_item",
        {"item": "Soda"},
        target={ATTR_ENTITY_ID: "todo.mealie_supermarket"},
        blocking=True,
    )

    mock_mealie_client.add_shopping_item.assert_called_once()


async def test_update_todo_list_item(
    hass: HomeAssistant,
    mock_mealie_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test for adding a To-do Item."""
    await setup_integration(hass, mock_config_entry)

    mock_mealie_client.update_shopping_item = AsyncMock()

    await hass.services.async_call(
        TODO_DOMAIN,
        "update_item",
        {"item": "aubergine", "rename": "Eggplant", "status": "completed"},
        target={ATTR_ENTITY_ID: "todo.mealie_supermarket"},
        blocking=True,
    )

    mock_mealie_client.update_shopping_item.assert_called_once()


async def test_delete_todo_list_item(
    hass: HomeAssistant,
    mock_mealie_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test for deleting a To-do Item."""
    await setup_integration(hass, mock_config_entry)

    mock_mealie_client.delete_shopping_item = AsyncMock()

    await hass.services.async_call(
        TODO_DOMAIN,
        "remove_item",
        {"item": "aubergine"},
        target={ATTR_ENTITY_ID: "todo.mealie_supermarket"},
        blocking=True,
    )

    mock_mealie_client.delete_shopping_item.assert_called_once()
