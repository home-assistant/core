"""Integration to integrate Keymitt BLE devices with Home Assistant."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

import bleak

from homeassistant.components import bluetooth
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady


@contextmanager
def patch_unused_bleak_discover_import() -> Generator[None]:
    """Patch bleak.discover import in microbot. It is unused and was removed in bleak 1.0.0."""

    def getattr_bleak(name: str) -> object:
        if name == "discover":
            return None
        raise AttributeError

    original_func = bleak.__dict__.get("__getattr__")
    bleak.__dict__["__getattr__"] = getattr_bleak
    try:
        yield
    finally:
        if original_func is not None:
            bleak.__dict__["__getattr__"] = original_func


with patch_unused_bleak_discover_import():
    from microbot import MicroBotApiClient

from .coordinator import (  # noqa: E402
    MicroBotConfigEntry,
    MicroBotDataUpdateCoordinator,
)

PLATFORMS: list[str] = [Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, entry: MicroBotConfigEntry) -> bool:
    """Set up this integration using UI."""
    token: str = entry.data[CONF_ACCESS_TOKEN]
    bdaddr: str = entry.data[CONF_ADDRESS]
    ble_device = bluetooth.async_ble_device_from_address(hass, bdaddr)
    if not ble_device:
        raise ConfigEntryNotReady(f"Could not find MicroBot with address {bdaddr}")
    client = MicroBotApiClient(
        device=ble_device,
        token=token,
    )
    coordinator = MicroBotDataUpdateCoordinator(
        hass, client=client, ble_device=ble_device
    )

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(coordinator.async_start())

    return True


async def async_unload_entry(hass: HomeAssistant, entry: MicroBotConfigEntry) -> bool:
    """Handle removal of an entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
