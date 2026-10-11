"""Tests for the Philips TV integration setup."""

from typing import Any

from homeassistant.components.philips_js.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import MOCK_MENU_STORAGE_KEY, MOCK_MENU_UNIQUE_ID

from tests.common import MockConfigEntry


async def test_remove_unselected_menu_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_menu_config_entry: MockConfigEntry,
) -> None:
    """Test entities of menu nodes that are no longer selected are removed."""
    entities = {
        unique_id: entity_registry.async_get_or_create(
            platform,
            DOMAIN,
            f"{MOCK_MENU_UNIQUE_ID}_{unique_id}",
            config_entry=mock_menu_config_entry,
        ).entity_id
        for platform, unique_id in (
            (Platform.SWITCH, "menu_2"),
            (Platform.NUMBER, "menu_7"),
            (Platform.NUMBER, "menu_17_org.droidtv.ui.strings.R.string.MAIN_RED"),
            (Platform.SWITCH, "screenstate"),
        )
    }

    assert await hass.config_entries.async_setup(mock_menu_config_entry.entry_id)
    await hass.async_block_till_done()

    assert {
        unique_id: entity_registry.async_get(entity_id) is not None
        for unique_id, entity_id in entities.items()
    } == {
        "menu_2": True,
        "menu_7": False,
        "menu_17_org.droidtv.ui.strings.R.string.MAIN_RED": False,
        "screenstate": True,
    }


async def test_remove_entry(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    mock_menu_config_entry: MockConfigEntry,
) -> None:
    """Test the stored menu is removed with the config entry."""
    assert await hass.config_entries.async_setup(mock_menu_config_entry.entry_id)
    await hass.async_block_till_done()
    assert MOCK_MENU_STORAGE_KEY in hass_storage

    await hass.config_entries.async_remove(mock_menu_config_entry.entry_id)
    await hass.async_block_till_done()

    assert MOCK_MENU_STORAGE_KEY not in hass_storage
