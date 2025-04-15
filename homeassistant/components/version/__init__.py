"""The Version integration."""

from __future__ import annotations

import logging

from pyhaversion import HaVersion

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    BOARD_MAP,
    CONF_BOARD,
    CONF_CHANNEL,
    CONF_IMAGE,
    CONF_SOURCE,
    PLATFORMS,
)
from .coordinator import VersionConfigEntry, VersionDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: VersionConfigEntry) -> bool:
    """Set up the version integration from a config entry."""

    board = entry.data[CONF_BOARD]

    if board not in BOARD_MAP:
        _LOGGER.error(
            'Board "%s" is (no longer) valid. Please remove the integration "%s"',
            board,
            entry.title,
        )
        return False

    coordinator = VersionDataUpdateCoordinator(
        hass=hass,
        config_entry=entry,
        api=HaVersion(
            session=async_get_clientsession(hass),
            source=entry.data[CONF_SOURCE],
            image=entry.data[CONF_IMAGE],
            board=BOARD_MAP[board],
            channel=entry.data[CONF_CHANNEL].lower(),
            timeout=30,
        ),
    )
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: VersionConfigEntry) -> bool:
    """Unload the config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
