"""HTTP views to interact with the device registry."""
import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.components.websocket_api.decorators import require_admin
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceEntryDisabler, async_get

WS_TYPE_LIST = "config/device_registry/list"
SCHEMA_WS_LIST = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend(
    {vol.Required("type"): WS_TYPE_LIST}
)

WS_TYPE_UPDATE = "config/device_registry/update"
SCHEMA_WS_UPDATE = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend(
    {
        vol.Required("type"): WS_TYPE_UPDATE,
        vol.Required("device_id"): str,
        vol.Optional("area_id"): vol.Any(str, None),
        vol.Optional("name_by_user"): vol.Any(str, None),
        # We only allow setting disabled_by user via API.
        # No Enum support like this in voluptuous, use .value
        vol.Optional("disabled_by"): vol.Any(DeviceEntryDisabler.USER.value, None),
    }
)


async def async_setup(hass):
    """Enable the Device Registry views."""
    websocket_api.async_register_command(
        hass, WS_TYPE_LIST, websocket_list_devices, SCHEMA_WS_LIST
    )
    websocket_api.async_register_command(
        hass, WS_TYPE_UPDATE, websocket_update_device, SCHEMA_WS_UPDATE
    )
    websocket_api.async_register_command(
        hass, websocket_remove_config_entry_from_device
    )
    return True


@callback
def websocket_list_devices(hass, connection, msg):
    """Handle list devices command."""
    registry = async_get(hass)
    connection.send_message(
        websocket_api.result_message(
            msg["id"], [_entry_dict(entry) for entry in registry.devices.values()]
        )
    )


@require_admin
@callback
def websocket_update_device(hass, connection, msg):
    """Handle update area websocket command."""
    registry = async_get(hass)

    msg.pop("type")
    msg_id = msg.pop("id")

    if msg.get("disabled_by") is not None:
        msg["disabled_by"] = DeviceEntryDisabler(msg["disabled_by"])

    entry = registry.async_update_device(**msg)

    connection.send_message(websocket_api.result_message(msg_id, _entry_dict(entry)))


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        "type": "config/device_registry/remove_config_entry",
        "device_id": str,
        "config_entry_id": str,
    }
)
@callback
def websocket_remove_config_entry_from_device(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Remove config entry from a device."""
    registry = async_get(hass)

    config_entry = hass.config_entries.async_get_entry(msg["config_entry_id"])
    if config_entry and not config_entry.supports_remove_device:
        connection.send_error(
            msg["id"],
            websocket_api.const.ERR_HOME_ASSISTANT_ERROR,
            "Config entry does not support device removal",
        )
        return

    try:
        entry = registry.async_update_device(
            msg["device_id"], remove_config_entry_id=msg["config_entry_id"]
        )
    except HomeAssistantError as exc:
        connection.send_error(
            msg["id"],
            websocket_api.const.ERR_HOME_ASSISTANT_ERROR,
            str(exc),
        )
        return
    except KeyError:
        connection.send_error(
            msg["id"], websocket_api.const.ERR_HOME_ASSISTANT_ERROR, "Unknown device"
        )
        return

    entry_as_dict = _entry_dict(entry) if entry else None

    connection.send_message(websocket_api.result_message(msg["id"], entry_as_dict))


@callback
def _entry_dict(entry):
    """Convert entry to API format."""
    return {
        "area_id": entry.area_id,
        "configuration_url": entry.configuration_url,
        "config_entries": list(entry.config_entries),
        "connections": list(entry.connections),
        "disabled_by": entry.disabled_by,
        "entry_type": entry.entry_type,
        "id": entry.id,
        "identifiers": list(entry.identifiers),
        "manufacturer": entry.manufacturer,
        "model": entry.model,
        "name_by_user": entry.name_by_user,
        "name": entry.name,
        "sw_version": entry.sw_version,
        "hw_version": entry.hw_version,
        "via_device_id": entry.via_device_id,
    }
