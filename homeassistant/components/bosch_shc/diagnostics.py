"""Diagnostics support for the Bosch SHC integration."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from . import BoschConfigEntry
from .const import CONF_SSL_CERTIFICATE, CONF_SSL_KEY

# async_redact_data matches by key name recursively, so both the config-entry
# keys and the device-level keys below are covered by one set. Device *names*
# are deliberately not redacted -- needed to correlate a report, not secret.
TO_REDACT = {
    CONF_HOST,
    CONF_SSL_CERTIFICATE,
    CONF_SSL_KEY,
    "macAddress",
    "shcIpAddress",
    "root_device_id",
    "serial",
    # device.id embeds a hardware address for Zigbee devices, e.g.
    # "hdm:ZigBee:5c0272fffe462481" -- same class of identifying data as
    # macAddress/serial/root_device_id above. Named "device_id" (not "id")
    # so this doesn't also redact service.id (e.g. "PowerSwitch"), which is
    # not identifying and is needed to read the dump.
    "device_id",
}


def _device_dump(device: Any) -> dict[str, Any]:
    """One device + the raw state of each of its services."""
    return {
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


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: BoschConfigEntry
) -> dict[str, Any]:
    """Return redacted diagnostics for a Bosch SHC config entry."""
    session = entry.runtime_data
    info = session.information

    return {
        "entry_data": async_redact_data(dict(entry.data), TO_REDACT),
        "shc": async_redact_data(
            {
                "version": info.version,
                "update_state": info.updateState.name,
                "macAddress": info.macAddress,
                "shcIpAddress": info.shcIpAddress,
            },
            TO_REDACT,
        ),
        "devices": [
            async_redact_data(_device_dump(device), TO_REDACT)
            for device in session.devices
        ],
    }
