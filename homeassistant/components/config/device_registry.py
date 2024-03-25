"""HTTP views to interact with the device registry."""

from __future__ import annotations

from typing import Any, cast

import voluptuous as vol

from homeassistant import loader
from homeassistant.components import websocket_api
from homeassistant.components.websocket_api.decorators import require_admin
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import (
    DeviceEntry,
    DeviceEntryDisabler,
    async_get,
)


@callback
def async_setup(hass: HomeAssistant) -> bool:
    """Enable the Device Registry views."""

    websocket_api.async_register_command(hass, websocket_list_devices)
    websocket_api.async_register_command(hass, websocket_update_device)
    websocket_api.async_register_command(
        hass, websocket_remove_config_entry_from_device
    )
    return True


@callback
@websocket_api.websocket_command(
    {
        vol.Required("type"): "config/device_registry/list",
    }
)
def websocket_list_devices(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Handle list devices command."""
    registry = async_get(hass)
    # Build start of response message
    msg_json_prefix = (
        f'{{"id":{msg["id"]},"type": "{websocket_api.const.TYPE_RESULT}",'
        f'"success":true,"result": ['
    ).encode()
    # Concatenate cached entity registry item JSON serializations
    inner = b",".join(
        [
            entry.json_repr
            for entry in registry.devices.values()
            if entry.json_repr is not None
        ]
    )
    msg_json = b"".join((msg_json_prefix, inner, b"]}"))
    connection.send_message(msg_json)


@require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "config/device_registry/update",
        vol.Optional("area_id"): vol.Any(str, None),
        vol.Required("device_id"): str,
        # We only allow setting disabled_by user via API.
        # No Enum support like this in voluptuous, use .value
        vol.Optional("disabled_by"): vol.Any(DeviceEntryDisabler.USER.value, None),
        vol.Optional("labels"): [str],
        vol.Optional("name_by_user"): vol.Any(str, None),
    }
)
@callback
def websocket_update_device(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Handle update device websocket command."""
    registry = async_get(hass)

    msg.pop("type")
    msg_id = msg.pop("id")

    if msg.get("disabled_by") is not None:
        msg["disabled_by"] = DeviceEntryDisabler(msg["disabled_by"])

    if "labels" in msg:
        # Convert labels to a set
        msg["labels"] = set(msg["labels"])

    entry = cast(DeviceEntry, registry.async_update_device(**msg))

    connection.send_message(websocket_api.result_message(msg_id, entry.dict_repr))


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        "type": "config/device_registry/remove_config_entry",
        "config_entry_id": str,
        "device_id": str,
    }
)
@websocket_api.async_response
async def websocket_remove_config_entry_from_device(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
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
        component = await integration.async_get_component()
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

    entry_as_dict = entry.dict_repr if entry else None

    connection.send_message(websocket_api.result_message(msg["id"], entry_as_dict))
