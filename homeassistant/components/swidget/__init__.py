"""The swidget integration."""

from __future__ import annotations

import logging
from typing import Any

from swidget.discovery import discover_single
from swidget.exceptions import SwidgetException
from swidget.swidgetdevice import SwidgetDevice

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, Platform
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
            host=entry.data[CONF_HOST],
            token_name="x-secret-key",
            password=entry.data[CONF_PASSWORD],
            use_https=True,
            use_websockets=True,
        )
    except SwidgetException as ex:
        raise ConfigEntryNotReady(
            f"Unable to connect to Swidget device to get metadata: {entry.data[CONF_HOST]}"
        ) from ex

    coordinator = SwidgetDataUpdateCoordinator(hass, device)
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as ex:
        raise ConfigEntryNotReady(
            f"Unable to to perform initial refresh: {entry.data[CONF_HOST]}"
        ) from ex
    hass.data[DOMAIN][entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    try:
        await device.start()
        hass.async_create_background_task(
            device.get_websocket().listen(), "websocket_connection"
        )
    except Exception as ex:
        raise ConfigEntryNotReady(
            f"Unable to connect to Swidget device over websockets: {entry.data[CONF_HOST]}"
        ) from ex
    if await coordinator.async_initialize():
        return True
    return False


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    hass_data: dict[str, Any] = hass.data[DOMAIN]
    device: SwidgetDevice = hass_data[entry.entry_id].device
    await device.stop()
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass_data.pop(entry.entry_id)
    return unload_ok
