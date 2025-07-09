"""The Philips TV integration."""

from __future__ import annotations

import logging

from haphilipsjs import PhilipsTV
from haphilipsjs.typing import SystemType

from homeassistant.const import (
    CONF_API_VERSION,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant

from .const import CONF_SYSTEM
from .coordinator import PhilipsTVConfigEntry, PhilipsTVDataUpdateCoordinator

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.LIGHT,
    Platform.MEDIA_PLAYER,
    Platform.REMOTE,
    Platform.SWITCH,
]

LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: PhilipsTVConfigEntry) -> bool:
    """Set up Philips TV from a config entry."""

    system: SystemType | None = entry.data.get(CONF_SYSTEM)
    tvapi = PhilipsTV(
        entry.data[CONF_HOST],
        entry.data[CONF_API_VERSION],
        username=entry.data.get(CONF_USERNAME),
        password=entry.data.get(CONF_PASSWORD),
        system=system,
    )
    coordinator = PhilipsTVDataUpdateCoordinator(hass, entry, tvapi)

    await coordinator.async_refresh()

    if (actual_system := tvapi.system) and actual_system != system:
        data = {**entry.data, CONF_SYSTEM: actual_system}
        hass.config_entries.async_update_entry(entry, data=data)

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_update_entry))

    return True


async def async_update_entry(hass: HomeAssistant, entry: PhilipsTVConfigEntry) -> None:
    """Update options."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: PhilipsTVConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
