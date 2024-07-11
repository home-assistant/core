"""The Vogel's MotionMount integration."""

from __future__ import annotations

import socket

import motionmount

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.device_registry import format_mac

from .const import DOMAIN, EMPTY_MAC

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Vogel's MotionMount from a config entry."""

    host = entry.data[CONF_HOST]

    # Create API instance
    mm = motionmount.MotionMount(host, entry.data[CONF_PORT])

    # Validate the API connection
    try:
        await mm.connect()
    except (ConnectionError, TimeoutError, socket.gaierror) as ex:
        raise ConfigEntryNotReady(f"Failed to connect to {host}") from ex

    found_mac = format_mac(mm.mac.hex())
    if found_mac not in (EMPTY_MAC, entry.unique_id):
        # If the mac address of the device does not match the unique_id
        # of the config entry, it likely means the DHCP lease has expired
        # and the device has been assigned a new IP address. We need to
        # wait for the next discovery to find the device at its new address
        # and update the config entry so we do not mix up devices.
        await mm.disconnect()
        raise ConfigEntryNotReady(
            f"Unexpected device found at {host}; expected {entry.unique_id}, found {found_mac}"
        )

    # Store an API object for your platforms to access
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = mm

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        mm: motionmount.MotionMount = hass.data[DOMAIN].pop(entry.entry_id)
        await mm.disconnect()

    return unload_ok
