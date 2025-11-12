"""The xbox integration."""

from __future__ import annotations

import logging

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .coordinator import (
    XboxConfigEntry,
    XboxConsolesCoordinator,
    XboxCoordinators,
    XboxUpdateCoordinator,
)

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.IMAGE,
    Platform.MEDIA_PLAYER,
    Platform.REMOTE,
    Platform.SENSOR,
]


async def async_setup_entry(hass: HomeAssistant, entry: XboxConfigEntry) -> bool:
    """Set up xbox from a config entry."""

    coordinator = XboxUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    consoles = XboxConsolesCoordinator(hass, entry, coordinator)

    entry.runtime_data = XboxCoordinators(coordinator, consoles)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    await async_migrate_unique_id(hass, entry)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: XboxConfigEntry) -> bool:
    """Unload a config entry."""

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_unique_id(hass: HomeAssistant, entry: XboxConfigEntry) -> bool:
    """Migrate config entry.

    Migration requires runtime data
    """

    if entry.version == 1 and entry.minor_version < 2:
        # Migrate unique_id from `xbox` to account xuid and
        # change generic entry name to user's gamertag
        coordinator = entry.runtime_data.status
        xuid = coordinator.client.xuid
        gamertag = coordinator.data.presence[xuid].gamertag

        return hass.config_entries.async_update_entry(
            entry,
            unique_id=xuid,
            title=(gamertag if entry.title == "Home Assistant Cloud" else entry.title),
            minor_version=2,
        )

    return True
