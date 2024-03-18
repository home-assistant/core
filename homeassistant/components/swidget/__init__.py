"""The swidget integration."""

from __future__ import annotations

import logging
from typing import Any

from swidget.discovery import discover_single
from swidget.exceptions import SwidgetException
from swidget.swidgetdevice import SwidgetDevice

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN
from .coordinator import SwidgetDataUpdateCoordinator

LOGGER = logging.getLogger(__name__)
PLATFORMS: list[Platform] = [Platform.LIGHT]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up swidget from a config entry."""

    hass.data.setdefault(DOMAIN, {})
    try:
        device = await discover_single(
            host=entry.data["host"],
            token_name="x-secret-key",
            password=entry.data["password"],
            use_https=True,
            use_websockets=True,
        )
    except SwidgetException as ex:
        raise ConfigEntryNotReady from ex

    hass.data[DOMAIN][entry.entry_id] = SwidgetDataUpdateCoordinator(hass, device)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await device.start()
    hass.loop.create_task(device.get_websocket().listen())
    await device.update()
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    hass_data: dict[str, Any] = hass.data[DOMAIN]
    device: SwidgetDevice = hass_data[entry.entry_id].device
    await device.stop()
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass_data.pop(entry.entry_id)
    return unload_ok
