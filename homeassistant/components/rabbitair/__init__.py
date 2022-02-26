"""The Rabbit Air integration."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging

from rabbitair import Client, State, UdpClient

from homeassistant.components import zeroconf
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_HOST,
    CONF_SCAN_INTERVAL,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN, KEY_COORDINATOR, KEY_DEVICE

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.FAN]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Rabbit Air from a config entry."""

    hass.data.setdefault(DOMAIN, {})

    host: str = entry.data[CONF_HOST]
    token: str = entry.data[CONF_ACCESS_TOKEN]

    zeroconf_instance = await zeroconf.async_get_async_instance(hass)
    device: Client = UdpClient(host, token, zeroconf=zeroconf_instance)

    scan_interval: int = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    update_interval = timedelta(seconds=scan_interval)

    async def async_update_data() -> State:
        try:
            return await device.get_state()
        except asyncio.TimeoutError:
            raise
        except Exception as err:
            raise UpdateFailed from err

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="rabbitair",
        update_method=async_update_data,
        update_interval=update_interval,
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        KEY_COORDINATOR: coordinator,
        KEY_DEVICE: device,
    }

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)
