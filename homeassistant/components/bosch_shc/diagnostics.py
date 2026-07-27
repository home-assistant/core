"""Diagnostics support for the Bosch SHC integration."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST, CONF_TOKEN
from homeassistant.core import HomeAssistant

from . import BoschConfigEntry
from .const import CONF_HOSTNAME, CONF_SSL_CERTIFICATE, CONF_SSL_KEY

# async_redact_data matches by key name recursively, so both the config-entry
# keys and the device-level keys below are covered by one set. Device *names*
# are deliberately not redacted -- needed to correlate a report, not secret.
TO_REDACT = {
    CONF_HOST,
    CONF_HOSTNAME,
    CONF_TOKEN,
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
    """One device + the state of each of its known services.

    boschshcpy only builds device_services for service IDs it recognizes
    (SUPPORTED_DEVICE_SERVICE_IDS); an unknown/unmapped service on a device
    won't appear here.
    """
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
    # SHCInformation exposes an updateState enum; the async
    # _AsyncSHCInformation counterpart exposes a plain update_state string
    # instead. Support both shapes since either can be the runtime type here.
    update_state_enum = getattr(info, "updateState", None)
    update_state = (
        update_state_enum.name
        if update_state_enum is not None
        else getattr(info, "update_state", None)
    )

    return {
        "entry_data": async_redact_data(dict(entry.data), TO_REDACT),
        "shc": async_redact_data(
            {
                "version": info.version,
                "update_state": update_state,
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
