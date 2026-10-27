"""Support for The Things network."""

import logging

from homeassistant.const import CONF_API_KEY, CONF_HOST
from homeassistant.core import HomeAssistant

from .const import PLATFORMS, TTN_API_HOST
from .coordinator import TTNConfigEntry, TTNCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: TTNConfigEntry) -> None:
    """Establish connection with The Things Network."""

    _LOGGER.debug(
        "Set up %s at %s",
        entry.data[CONF_API_KEY],
        entry.data.get(CONF_HOST, TTN_API_HOST),
    )

    coordinator = TTNCoordinator(hass, entry)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: TTNConfigEntry) -> None:
    """Unload a config entry."""

    _LOGGER.debug(
        "Remove %s at %s",
        entry.data[CONF_API_KEY],
        entry.data.get(CONF_HOST, TTN_API_HOST),
    )

    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
