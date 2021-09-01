"""API interface to get an Insteon device."""

from pyinsteon import devices
import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant

from ..const import (
    DEVICE_ID,
    DOMAIN,
    HA_DEVICE_NOT_FOUND,
    ID,
    INSTEON_DEVICE_NOT_FOUND,
    TYPE,
)


def compute_device_name(ha_device):
    """Return the HA device name."""
    return ha_device.name_by_user if ha_device.name_by_user else ha_device.name


def get_insteon_device_from_ha_device(ha_device):
    """Return the Insteon device from an HA device."""
    for identifier in ha_device.identifiers:
        if len(identifier) > 1 and identifier[0] == DOMAIN and devices[identifier[1]]:
            return devices[identifier[1]]
    return None


async def async_device_name(dev_registry, address):
    """Get the Insteon device name from a device registry id."""
    ha_device = dev_registry.async_get_device(
        identifiers={(DOMAIN, str(address))}, connections=set()
    )
    if not ha_device:
        device = devices[address]
        if device:
            return f"{device.description} ({device.model})"
        return ""
    return compute_device_name(ha_device)


def notify_device_not_found(connection, msg, text):
    """Notify the caller that the device was not found."""
    connection.send_message(
        websocket_api.error_message(msg[ID], websocket_api.const.ERR_NOT_FOUND, text)
    )


@websocket_api.websocket_command(
    {vol.Required(TYPE): "insteon/device/get", vol.Required(DEVICE_ID): str}
)
@websocket_api.require_admin
@websocket_api.async_response
async def websocket_get_device(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: dict,
) -> None:
    """Get an Insteon device."""
    dev_registry = await hass.helpers.device_registry.async_get_registry()
    ha_device = dev_registry.async_get(msg[DEVICE_ID])
    if not ha_device:
        notify_device_not_found(connection, msg, HA_DEVICE_NOT_FOUND)
        return
    device = get_insteon_device_from_ha_device(ha_device)
    if not device:
        notify_device_not_found(connection, msg, INSTEON_DEVICE_NOT_FOUND)
        return
    ha_name = compute_device_name(ha_device)
    device_info = {
        "name": ha_name,
        "address": str(device.address),
        "is_battery": device.is_battery,
        "aldb_status": str(device.aldb.status),
    }
    connection.send_result(msg[ID], device_info)
