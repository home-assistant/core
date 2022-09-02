"""HTTP views to interact with the device registry."""
from __future__ import annotations

import voluptuous as vol

from homeassistant import loader
from homeassistant.components import websocket_api
from homeassistant.components.websocket_api.decorators import require_admin
from homeassistant.components.websocket_api.messages import (
    IDEN_JSON_TEMPLATE,
    IDEN_TEMPLATE,
    message_to_json,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import (
    EVENT_DEVICE_REGISTRY_UPDATED,
    DeviceEntryDisabler,
    async_get,
)

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

    cached_list_devices: str | None = None

    @callback
    def _async_clear_list_device_cache(event: Event) -> None:
        nonlocal cached_list_devices
        cached_list_devices = None

    @callback
    def websocket_list_devices(hass, connection, msg):
        """Handle list devices command."""
        nonlocal cached_list_devices
        if not cached_list_devices:
            registry = async_get(hass)
            cached_list_devices = message_to_json(
                websocket_api.result_message(
                    IDEN_TEMPLATE,
                    [_entry_dict(entry) for entry in registry.devices.values()],
                )
            )
        connection.send_message(
            cached_list_devices.replace(IDEN_JSON_TEMPLATE, str(msg["id"]), 1)
        )

    hass.bus.async_listen(
        EVENT_DEVICE_REGISTRY_UPDATED,
        _async_clear_list_device_cache,
        run_immediately=True,
    )

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
@websocket_api.async_response
async def websocket_remove_config_entry_from_device(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Remove config entry from a device."""
    registry = async_get(hass)
    config_entry_id = msg["config_entry_id"]
    device_id = msg["device_id"]

    if (config_entry := hass.config_entries.async_get_entry(config_entry_id)) is None:
        raise HomeAssistantError("Unknown config entry")

    if not config_entry.supports_remove_device:
        raise HomeAssistantError("Config entry does not support device removal")

    if (device_entry := registry.async_get(device_id)) is None:
        raise HomeAssistantError("Unknown device")

    if config_entry_id not in device_entry.config_entries:
        raise HomeAssistantError("Config entry not in device")

    try:
        integration = await loader.async_get_integration(hass, config_entry.domain)
        component = integration.get_component()
    except (ImportError, loader.IntegrationNotFound) as exc:
        raise HomeAssistantError("Integration not found") from exc

    if not await component.async_remove_config_entry_device(
        hass, config_entry, device_entry
    ):
        raise HomeAssistantError(
            "Failed to remove device entry, rejected by integration"
        )

    entry = registry.async_update_device(
        device_id, remove_config_entry_id=config_entry_id
    )

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
        "hw_version": entry.hw_version,
        "id": entry.id,
        "identifiers": list(entry.identifiers),
        "manufacturer": entry.manufacturer,
        "model": entry.model,
        "name_by_user": entry.name_by_user,
        "name": entry.name,
        "sw_version": entry.sw_version,
        "via_device_id": entry.via_device_id,
    }
