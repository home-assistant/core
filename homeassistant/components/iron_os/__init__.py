"""The IronOS integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from pynecil import IronOSUpdate, Pynecil

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util.hass_dict import HassKey

from .const import DOMAIN
from .coordinator import (
    IronOSConfigEntry,
    IronOSCoordinators,
    IronOSFirmwareUpdateCoordinator,
    IronOSLiveDataCoordinator,
    IronOSSettingsCoordinator,
)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.UPDATE,
]


IRON_OS_KEY: HassKey[IronOSFirmwareUpdateCoordinator] = HassKey(DOMAIN)


_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: IronOSConfigEntry) -> bool:
    """Set up IronOS from a config entry."""
    if IRON_OS_KEY not in hass.data:
        session = async_get_clientsession(hass)
        github = IronOSUpdate(session)

        hass.data[IRON_OS_KEY] = IronOSFirmwareUpdateCoordinator(hass, github)
        await hass.data[IRON_OS_KEY].async_request_refresh()

    if TYPE_CHECKING:
        assert entry.unique_id

    device = Pynecil(entry.unique_id)

    live_data = IronOSLiveDataCoordinator(hass, entry, device)
    await live_data.async_config_entry_first_refresh()

    settings = IronOSSettingsCoordinator(hass, entry, device)
    await settings.async_config_entry_first_refresh()

    entry.runtime_data = IronOSCoordinators(
        live_data=live_data,
        settings=settings,
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: IronOSConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if not hass.config_entries.async_loaded_entries(DOMAIN):
        await hass.data[IRON_OS_KEY].async_shutdown()
        hass.data.pop(IRON_OS_KEY)
    return unload_ok
