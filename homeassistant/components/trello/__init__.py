"""The Trello integration."""

from __future__ import annotations

from trello import TrelloClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_API_TOKEN, Platform
from homeassistant.core import HomeAssistant

from .const import CONF_BOARD_IDS, DOMAIN
from .coordinator import TrelloDataUpdateCoordinator

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up from a config entry."""
    config_boards = entry.options[CONF_BOARD_IDS]
    config_data = entry.data
    trello_client = TrelloClient(
        api_key=config_data[CONF_API_KEY],
        api_secret=config_data[CONF_API_TOKEN],
    )
    trello_coordinator = TrelloDataUpdateCoordinator(hass, trello_client, config_boards)
    await trello_coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = trello_coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    return True


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle removal of an entry."""
    await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
