"""Web socket API for Insteon devices."""

from typing import Any

from pyinsteon import devices
from pyinsteon.constants import ALDBStatus
import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr

from ..const import DEVICE_ADDRESS, ID, INSTEON_DEVICE_NOT_FOUND, TYPE
from ..utils import async_device_name
from .device import notify_device_not_found

ALDB_RECORD = "record"
ALDB_RECORD_SCHEMA = vol.Schema(
    {
        vol.Required("mem_addr"): int,
        vol.Required("in_use"): bool,
        vol.Required("group"): vol.Range(0, 255),
        vol.Required("is_controller"): bool,
        vol.Optional("highwater"): bool,
        vol.Required("target"): str,
        vol.Optional("target_name"): str,
        vol.Required("data1"): vol.Range(0, 255),
        vol.Required("data2"): vol.Range(0, 255),
        vol.Required("data3"): vol.Range(0, 255),
        vol.Optional("dirty"): bool,
    }
)


async def async_aldb_record_to_dict(dev_registry, record, dirty=False):
    """Convert an ALDB record to a dict."""
    return ALDB_RECORD_SCHEMA(
        {
            "mem_addr": record.mem_addr,
            "in_use": record.is_in_use,
            "is_controller": record.is_controller,
            "highwater": record.is_high_water_mark,
            "group": record.group,
            "target": str(record.target),
            "target_name": await async_device_name(dev_registry, record.target),
            "data1": record.data1,
            "data2": record.data2,
            "data3": record.data3,
            "dirty": dirty,
        }
    )


async def async_reload_and_save_aldb(hass, device):
    """Add default links to an Insteon device."""
    if device == devices.modem:
        await device.aldb.async_load()
    else:
        await device.aldb.async_load(refresh=True)
    await devices.async_save(workdir=hass.config.config_dir)


def any_aldb_loading() -> bool:
    """Identify if any All-Link Databases are loading."""
    return any(
        device.aldb.status == ALDBStatus.LOADING for _, device in devices.items()
    )


@websocket_api.websocket_command(
    {vol.Required(TYPE): "insteon/aldb/get", vol.Required(DEVICE_ADDRESS): str}
)
@websocket_api.require_admin
@websocket_api.async_response
async def websocket_get_aldb(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Get the All-Link Database for an Insteon device."""
    if not (device := devices[msg[DEVICE_ADDRESS]]):
        notify_device_not_found(connection, msg, INSTEON_DEVICE_NOT_FOUND)
        return

    # Convert the ALDB to a dict merge in pending changes
    aldb = {mem_addr: device.aldb[mem_addr] for mem_addr in device.aldb}
    aldb.update(device.aldb.pending_changes)
    changed_records = list(device.aldb.pending_changes.keys())

    dev_registry = dr.async_get(hass)

    records = [
        await async_aldb_record_to_dict(
            dev_registry, aldb[mem_addr], mem_addr in changed_records
        )
        for mem_addr in aldb
    ]

    connection.send_result(msg[ID], records)


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "insteon/aldb/change",
        vol.Required(DEVICE_ADDRESS): str,
        vol.Required(ALDB_RECORD): ALDB_RECORD_SCHEMA,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def websocket_change_aldb_record(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Change an All-Link Database record for an Insteon device."""
    if not (device := devices[msg[DEVICE_ADDRESS]]):
        notify_device_not_found(connection, msg, INSTEON_DEVICE_NOT_FOUND)
        return

    record = msg[ALDB_RECORD]
    device.aldb.modify(
        mem_addr=record["mem_addr"],
        in_use=record["in_use"],
        group=record["group"],
        controller=record["is_controller"],
        target=record["target"],
        data1=record["data1"],
        data2=record["data2"],
        data3=record["data3"],
    )
    connection.send_result(msg[ID])


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "insteon/aldb/create",
        vol.Required(DEVICE_ADDRESS): str,
        vol.Required(ALDB_RECORD): ALDB_RECORD_SCHEMA,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def websocket_create_aldb_record(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Create an All-Link Database record for an Insteon device."""
    if not (device := devices[msg[DEVICE_ADDRESS]]):
        notify_device_not_found(connection, msg, INSTEON_DEVICE_NOT_FOUND)
        return

    record = msg[ALDB_RECORD]
    device.aldb.add(
        group=record["group"],
        controller=record["is_controller"],
        target=record["target"],
        data1=record["data1"],
        data2=record["data2"],
        data3=record["data3"],
    )
    connection.send_result(msg[ID])


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "insteon/aldb/write",
        vol.Required(DEVICE_ADDRESS): str,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def websocket_write_aldb(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Create an All-Link Database record for an Insteon device."""
    if not (device := devices[msg[DEVICE_ADDRESS]]):
        notify_device_not_found(connection, msg, INSTEON_DEVICE_NOT_FOUND)
        return

    await device.aldb.async_write()
    hass.async_create_task(async_reload_and_save_aldb(hass, device))
    connection.send_result(msg[ID])


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "insteon/aldb/load",
        vol.Required(DEVICE_ADDRESS): str,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def websocket_load_aldb(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Create an All-Link Database record for an Insteon device."""
    if not (device := devices[msg[DEVICE_ADDRESS]]):
        notify_device_not_found(connection, msg, INSTEON_DEVICE_NOT_FOUND)
        return

    hass.async_create_task(async_reload_and_save_aldb(hass, device))
    connection.send_result(msg[ID])


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "insteon/aldb/reset",
        vol.Required(DEVICE_ADDRESS): str,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def websocket_reset_aldb(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Create an All-Link Database record for an Insteon device."""
    if not (device := devices[msg[DEVICE_ADDRESS]]):
        notify_device_not_found(connection, msg, INSTEON_DEVICE_NOT_FOUND)
        return

    device.aldb.clear_pending()
    connection.send_result(msg[ID])


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "insteon/aldb/add_default_links",
        vol.Required(DEVICE_ADDRESS): str,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def websocket_add_default_links(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Add the default All-Link Database records for an Insteon device."""
    if not (device := devices[msg[DEVICE_ADDRESS]]):
        notify_device_not_found(connection, msg, INSTEON_DEVICE_NOT_FOUND)
        return

    device.aldb.clear_pending()
    await device.async_add_default_links()
    hass.async_create_task(async_reload_and_save_aldb(hass, device))
    connection.send_result(msg[ID])


@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "insteon/aldb/notify",
        vol.Required(DEVICE_ADDRESS): str,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def websocket_notify_on_aldb_status(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Tell Insteon a new ALDB record was added."""
    if not (device := devices[msg[DEVICE_ADDRESS]]):
        notify_device_not_found(connection, msg, INSTEON_DEVICE_NOT_FOUND)
        return

    @callback
    def record_added(record, sender, deleted):
        """Forward ALDB events to websocket."""
        forward_data = {"type": "record_loaded"}
        connection.send_message(websocket_api.event_message(msg["id"], forward_data))

    @callback
    def aldb_loaded(status):
        """Forward ALDB loaded event to websocket."""
        forward_data = {
            "type": "status_changed",
            "is_loading": status == ALDBStatus.LOADING,
        }
        connection.send_message(websocket_api.event_message(msg["id"], forward_data))

    @callback
    def async_cleanup() -> None:
        """Remove signal listeners."""
        device.aldb.unsubscribe_record_changed(record_added)
        device.aldb.unsubscribe_status_changed(aldb_loaded)

        forward_data = {"type": "unsubscribed"}
        connection.send_message(websocket_api.event_message(msg["id"], forward_data))

    connection.subscriptions[msg["id"]] = async_cleanup
    device.aldb.subscribe_record_changed(record_added)
    device.aldb.subscribe_status_changed(aldb_loaded)

    connection.send_result(msg[ID])


@websocket_api.websocket_command({vol.Required(TYPE): "insteon/aldb/notify_all"})
@websocket_api.require_admin
@websocket_api.async_response
async def websocket_notify_on_aldb_status_all(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Tell Insteon all ALDBs are loaded."""

    @callback
    def aldb_status_changed(status: ALDBStatus) -> None:
        """Forward ALDB loaded event to websocket."""

        forward_data = {
            "type": "status",
            "is_loading": any_aldb_loading(),
        }
        connection.send_message(websocket_api.event_message(msg["id"], forward_data))

    @callback
    def async_cleanup() -> None:
        """Remove signal listeners."""
        for device in devices.values():
            device.aldb.unsubscribe_status_changed(aldb_status_changed)

        forward_data = {"type": "unsubscribed"}
        connection.send_message(websocket_api.event_message(msg["id"], forward_data))

    connection.subscriptions[msg["id"]] = async_cleanup
    for device in devices.values():
        device.aldb.subscribe_status_changed(aldb_status_changed)

    connection.send_result(msg[ID])

    forward_data = {
        "type": "status",
        "is_loading": any_aldb_loading(),
    }
    connection.send_message(websocket_api.event_message(msg["id"], forward_data))
