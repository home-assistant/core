"""Diagnostics support for Tasmota."""

from typing import TYPE_CHECKING, Any

from hatasmota.const import CONF_HOSTNAME, CONF_IP, CONF_MAC, CONF_TOPIC

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .discovery import DISCOVERY_DATA

# The default topic contains part of the MAC address
TO_REDACT = {CONF_HOSTNAME, CONF_IP, CONF_MAC, CONF_TOPIC}


async def async_get_device_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry, device: dr.AnyDeviceEntry
) -> dict[str, Any]:
    """Return diagnostics for a device."""
    if TYPE_CHECKING:
        assert isinstance(device, dr.DeviceEntry)
    macs = {
        mac
        for connection_type, mac in device.connections
        if connection_type == dr.CONNECTION_NETWORK_MAC
    }
    discovery_payload = next(
        (
            payload
            for mac, payload in hass.data[DISCOVERY_DATA].items()
            if dr.format_mac(mac) in macs
        ),
        None,
    )
    if discovery_payload is None:
        return {"discovery_payload": None}
    return {"discovery_payload": async_redact_data(discovery_payload, TO_REDACT)}
