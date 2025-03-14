"""API interface to get an Insteon device."""

from typing import Any

from pyinsteon import devices
from pyinsteon.address import Address
from pyinsteon.constants import DeviceAction
import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_send

from ..const import (
    DEVICE_ADDRESS,
    DEVICE_ID,
    DOMAIN,
    HA_DEVICE_NOT_FOUND,
    ID,
    INSTEON_DEVICE_NOT_FOUND,
    MULTIPLE,
    SIGNAL_REMOVE_HA_DEVICE,
    SIGNAL_REMOVE_INSTEON_DEVICE,
    SIGNAL_REMOVE_X10_DEVICE,
    TYPE,
)
from ..schemas import build_x10_schema
from ..utils import compute_device_name
from .config import add_x10_device, remove_device_override, remove_x10_device

X10_DEVICE = "x10_device"
X10_DEVICE_SCHEMA = build_x10_schema()
REMOVE_ALL_REFS = "remove_all_refs"


async def async_add_devices(address, multiple):
    """Add one or more Insteon devices."""
    async for _ in devices.async_add_device(address=address, multiple=multiple):
        pass


def get_insteon_device_from_ha_device(ha_device):
    """Return the Insteon device from an HA device."""
    for identifier in ha_device.identifiers:
        if len(identifier) > 1 and identifier[0] == DOMAIN and devices[identifier[1]]:
            return devices[identifier[1]]
    return None


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
    msg: dict[str, Any],
) -> None:
    """Get an Insteon device."""
    dev_registry = dr.async_get(hass)
    if not (ha_device := dev_registry.async_get(msg[DEVICE_ID])):
        notify_device_not_found(connection, msg, HA_DEVICE_NOT_FOUND)
        return
    if not (device := get_insteon_device_from_ha_device(ha_device)):
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


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "insteon/device/add",
        vol.Required(MULTIPLE): bool,
        vol.Optional(DEVICE_ADDRESS): str,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def websocket_add_device(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Add one or more Insteon devices."""

    @callback
    def linking_complete(address: str, action: DeviceAction):
        """Forward device events to websocket."""
        if action == DeviceAction.COMPLETED:
            forward_data = {"type": "linking_stopped", "address": ""}
        else:
            return
        connection.send_message(websocket_api.event_message(msg["id"], forward_data))

    @callback
    def async_cleanup() -> None:
        """Remove signal listeners."""
        devices.unsubscribe(linking_complete)

    connection.subscriptions[msg["id"]] = async_cleanup
    devices.subscribe(linking_complete)

    async for address in devices.async_add_device(
        address=msg.get(DEVICE_ADDRESS), multiple=msg[MULTIPLE]
    ):
        forward_data = {"type": "device_added", "address": str(address)}
        connection.send_message(websocket_api.event_message(msg["id"], forward_data))

    connection.send_result(msg[ID])


@websocket_api.websocket_command({vol.Required(TYPE): "insteon/device/add/cancel"})
@websocket_api.require_admin
@websocket_api.async_response
async def websocket_cancel_add_device(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Cancel the Insteon all-linking process."""
    await devices.async_cancel_all_linking()
    connection.send_result(msg[ID])


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "insteon/device/remove",
        vol.Required(DEVICE_ADDRESS): str,
        vol.Required(REMOVE_ALL_REFS): bool,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def websocket_remove_device(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Remove an Insteon device."""

    address = msg[DEVICE_ADDRESS]
    remove_all_refs = msg[REMOVE_ALL_REFS]
    if address.startswith("X10"):
        _, housecode, unitcode = address.split(".")
        unitcode = int(unitcode)
        async_dispatcher_send(hass, SIGNAL_REMOVE_X10_DEVICE, housecode, unitcode)
        remove_x10_device(hass, housecode, unitcode)
    else:
        address = Address(address)
        remove_device_override(hass, address)
        async_dispatcher_send(hass, SIGNAL_REMOVE_HA_DEVICE, address)
        async_dispatcher_send(
            hass, SIGNAL_REMOVE_INSTEON_DEVICE, address, remove_all_refs
        )

    connection.send_result(msg[ID])


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "insteon/device/add_x10",
        vol.Required(X10_DEVICE): X10_DEVICE_SCHEMA,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def websocket_add_x10_device(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Get the schema for the X10 devices configuration."""
    x10_device = msg[X10_DEVICE]
    try:
        add_x10_device(hass, x10_device)
    except ValueError:
        connection.send_error(msg[ID], code="duplicate", message="Duplicate X10 device")
        return

    connection.send_result(msg[ID])
