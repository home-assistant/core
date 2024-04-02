"""Senziio integration."""

from __future__ import annotations

import logging

from homeassistant.components import mqtt
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MODEL, CONF_UNIQUE_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN, MANUFACTURER
from .device import SenziioDevice

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Senziio device from a config entry."""

    # Make sure MQTT integration is enabled and the client is available.
    if not await mqtt.async_wait_for_mqtt_client(hass):
        _LOGGER.error("MQTT integration is not available")
        return False

    device_id = entry.data[CONF_UNIQUE_ID]
    device_model = entry.data[CONF_MODEL]
    device = SenziioDevice(device_id, device_model, hass)

    registry_info = DeviceInfo(
        identifiers={(DOMAIN, device_id)},
        name=entry.title,
        manufacturer=MANUFACTURER,
        model=device_model,
        hw_version=entry.data["hw-version"],
        sw_version=entry.data["fw-version"],
        serial_number=entry.data["serial-number"],
        connections={(dr.CONNECTION_NETWORK_MAC, entry.data["mac-address"])},
    )
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        **registry_info,
    )

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = device

    # forward setup to all platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
