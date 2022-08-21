"""Integration to integrate MicroBot with Home Assistant."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from microbot import MicroBotApiClient

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN
from .coordinator import MicroBotDataUpdateCoordinator

if TYPE_CHECKING:
    from bleak.backends.device import BLEDevice

_LOGGER: logging.Logger = logging.getLogger(__package__)
PLATFORMS: list[str] = [Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up this integration using UI."""
    hass.data.setdefault(DOMAIN, {})
    token: str = entry.data[CONF_ACCESS_TOKEN]
    bdaddr: str = entry.data[CONF_ADDRESS]
    ble_device: BLEDevice | None = bluetooth.async_ble_device_from_address(hass, bdaddr)
    if not ble_device:
        raise ConfigEntryNotReady(f"Could not find MicroBot with address {bdaddr}")
    client = MicroBotApiClient(
        device=ble_device,
        token=token,
    )
    coordinator = MicroBotDataUpdateCoordinator(
        hass, client=client, ble_device=ble_device
    )

    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(coordinator.async_start())

    async def calibrate(call: ServiceCall) -> None:
        _LOGGER.debug("Calibrate service called")
        depth = call.data["depth"]
        duration = call.data["duration"]
        mode = call.data["mode"]
        await coordinator.api.calibrate(depth, duration, mode)

    hass.services.async_register(DOMAIN, "calibrate", calibrate)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle removal of an entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
