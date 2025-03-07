"""The Aeroflex Adjustable Bed integration."""

from __future__ import annotations

import logging

from bleak import BleakClient
from bleak.exc import BleakError

from homeassistant.components.bluetooth import async_ble_device_from_address
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_DEVICE_ADDRESS, CONF_DEVICE_NAME, DOMAIN, SERVICE_UUID

_LOGGER = logging.getLogger(__name__)
_PLATFORMS: list[Platform] = [Platform.NUMBER]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Aeroflex Adjustable Bed from a config entry."""
    address = entry.data.get(CONF_DEVICE_ADDRESS)
    name = entry.data.get(CONF_DEVICE_NAME)

    if not address:
        _LOGGER.error("No device address found in config entry")
        return False

    ble_device = async_ble_device_from_address(hass, address, connectable=True)

    if not ble_device:
        raise ConfigEntryNotReady(
            f"Could not find BLE device with name '{name}' at address {address}"
        )

    # Verify we can connect to the device
    try:
        async with BleakClient(ble_device) as client:
            if not client.is_connected:
                raise ConfigEntryNotReady(
                    f"Failed to connect to device '{name}' at address {address}"
                )

            # Check if the device has the required service
            if not any(
                service.uuid.lower() == SERVICE_UUID.lower()
                for service in client.services
            ):
                _LOGGER.error(
                    "Device '%s' at address %s does not have the required service UUID %s",
                    name,
                    address,
                    SERVICE_UUID,
                )
                return False
    except BleakError as err:
        raise ConfigEntryNotReady(
            f"Failed to connect to device '{name}' at address {address}: {err}"
        ) from err

    # Store BLE device in runtime data for use by the entities
    entry.runtime_data = ble_device

    # Store entry for later use
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = ble_device

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        if not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN)

    return unload_ok
