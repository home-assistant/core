"""Support for the Skybell HD Doorbell."""
from __future__ import annotations

import asyncio

from aioskybell import Skybell
from aioskybell.exceptions import SkybellAuthenticationException, SkybellException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .coordinator import SkybellDataUpdateCoordinator

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.CAMERA,
    Platform.LIGHT,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Skybell from a config entry."""
    email = entry.data[CONF_EMAIL]
    password = entry.data[CONF_PASSWORD]

    api = Skybell(
        username=email,
        password=password,
        get_devices=True,
        cache_path=hass.config.path(f"./skybell_{entry.unique_id}.pickle"),
        session=async_get_clientsession(hass),
    )
    try:
        devices = await api.async_initialize()
    except SkybellAuthenticationException as ex:
        raise ConfigEntryAuthFailed from ex
    except SkybellException as ex:
        raise ConfigEntryNotReady(f"Unable to connect to Skybell service: {ex}") from ex

    device_coordinators: list[SkybellDataUpdateCoordinator] = [
        SkybellDataUpdateCoordinator(hass, device) for device in devices
    ]
    await asyncio.gather(
        *[
            coordinator.async_config_entry_first_refresh()
            for coordinator in device_coordinators
        ]
    )
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = device_coordinators
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
