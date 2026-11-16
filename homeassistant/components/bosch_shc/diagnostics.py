"""Diagnostics support for Bosch SHC."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST, CONF_TOKEN
from homeassistant.core import HomeAssistant

from . import BoschConfigEntry
from .const import CONF_HOSTNAME, CONF_SSL_CERTIFICATE, CONF_SSL_KEY

TO_REDACT = {
    CONF_HOST,
    CONF_HOSTNAME,
    CONF_TOKEN,
    CONF_HOSTNAME,
    CONF_SSL_CERTIFICATE,
    CONF_SSL_KEY,
    CONF_TOKEN,
    "device_id",
    "ip",
    "macAddress",
    "root_device_id",
    "serial",
    "unique_id",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: BoschConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    session = entry.runtime_data
    info = session.information

    return async_redact_data(
        {
            "entry": dict(entry.data),
            "shc": {
                "version": info.version,
                "update_state": info.updateState.name,
                "macAddress": info.macAddress,
                "ip": info.shcIpAddress,
            },
            "devices": [
                {
                    "device_id": device.id,
                    "root_device_id": device.root_device_id,
                    "device_model": device.device_model,
                    "manufacturer": device.manufacturer,
                    "name": device.name,
                    "room_id": device.room_id,
                    "serial": device.serial,
                    "services": [
                        {"id": service.id, "state": service.state}
                        for service in device.device_services
                    ],
                }
                for device in session.devices
            ],
        },
        TO_REDACT,
    )
