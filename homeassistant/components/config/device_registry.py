"""HTTP views to interact with the device registry."""

from itertools import chain
import logging
from typing import Any

import voluptuous as vol

from homeassistant import loader
from homeassistant.components import websocket_api
from homeassistant.components.websocket_api import require_admin
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, label_registry as lr
from homeassistant.helpers.device_registry import DeviceEntryDisabler

_LOGGER = logging.getLogger(__name__)


@callback
def async_setup(hass: HomeAssistant) -> bool:
    """Enable the Device Registry views."""

    websocket_api.async_register_command(hass, websocket_list_composite_splits)
    websocket_api.async_register_command(hass, websocket_list_devices)
    websocket_api.async_register_command(hass, websocket_list_linked_devices)
    websocket_api.async_register_command(hass, websocket_update_device)
    websocket_api.async_register_command(hass, websocket_remove_device)
    websocket_api.async_register_command(
        hass, websocket_remove_config_entry_from_device
    )
    return True


@callback
@websocket_api.websocket_command(
    {
        vol.Required("type"): "config/device_registry/list_composite_splits",
    }
)
def websocket_list_composite_splits(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Handle list composite device splits command.

    Maps every pre-migration composite device id that was removed by splitting the
    device into one device per config entry to the ids of the devices which replaced
    it, and which of those (if any) belongs to the composite's former primary config
    entry.
    """
    registry = dr.async_get(hass)
    connection.send_result(
        msg["id"],
        {
            composite_id: {
                "split_ids": [device.id for device in devices],
                "primary_id": next(
                    (
                        device.id
                        for device in devices
                        if device.config_entry_id
                        == device.composite_primary_config_entry
                    ),
                    None,
                ),
            }
            for composite_id, devices in registry._devices.get_composite_splits().items()  # noqa: SLF001
        },
    )


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
    registry = dr.async_get(hass)
    # Build start of response message
    msg_json_prefix = (
        f'{{"id":{msg["id"]},"type": "{websocket_api.TYPE_RESULT}",'
        f'"success":true,"result": ['
    ).encode()
    # Concatenate cached entity registry item JSON serializations
    inner = b",".join(
        [
            entry.json_repr
            for entry in chain(registry.devices, registry.child_devices)
            if entry.json_repr is not None
        ]
    )
    msg_json = b"".join((msg_json_prefix, inner, b"]}"))
    connection.send_message(msg_json)


@callback
@websocket_api.websocket_command(
    {
        vol.Required("type"): "config/device_registry/list_linked_devices",
        vol.Required("device_id"): str,
    }
)
def websocket_list_linked_devices(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Handle list linked devices command.

    Linked devices share at least one connection or identifier with the given
    device. Each such connection or identifier is unique within a config entry, so
    the linked devices belong to other config entries.
    """
    registry = dr.async_get(hass)
    device_id = msg["device_id"]

    if (device := registry.async_get(device_id)) is None:
        connection.send_error(
            msg["id"], websocket_api.ERR_NOT_FOUND, "Device not found"
        )
        return

    # A child device is never linked: its identifiers share the parent's
    # per-config-entry namespace, so matching them against other entries' main
    # devices is not meaningful.
    if isinstance(device, dr.ChildDeviceEntry):
        connection.send_result(msg["id"], {"linked_devices": []})
        return

    linked_devices = [
        entry.id
        for entry in registry.async_get_devices(
            identifiers=device.identifiers,
            connections=device.connections,
        )
        if entry.id != device_id
    ]

    connection.send_result(msg["id"], {"linked_devices": linked_devices})


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
    registry = dr.async_get(hass)

    msg.pop("type")
    msg_id = msg.pop("id")

    if msg.get("disabled_by") is not None:
        msg["disabled_by"] = DeviceEntryDisabler(msg["disabled_by"])

    if "labels" in msg:
        labels = set(msg["labels"])
        msg["labels"] = labels - lr.async_get_missing_label_ids(hass, labels)

    device_id = msg["device_id"]

    # A composite device id has no single underlying device to update; reject it.
    if (
        registry.async_get(
            device_id, include_main_devices=False, include_child_devices=False
        )
        is not None
    ):
        connection.send_error(
            msg_id, websocket_api.ERR_NOT_ALLOWED, "Cannot update a composite device"
        )
        return
    if (
        device := registry.async_get(device_id, include_composite_devices=False)
    ) is None:
        connection.send_error(msg_id, websocket_api.ERR_NOT_FOUND, "Device not found")
        return

    entry: dr.AnyDeviceEntry | None
    if isinstance(device, dr.ChildDeviceEntry):
        entry = registry.async_update_child_device(**msg)
    else:
        entry = registry.async_update_device(**msg)
    assert entry is not None

    connection.send_message(websocket_api.result_message(msg_id, entry.dict_repr))


async def _async_remove_device(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
    *,
    expected_config_entry_id: str | None = None,
) -> None:
    """Remove a device.

    Shared implementation for the config/device_registry/remove command and its
    deprecated config/device_registry/remove_config_entry alias. The alias passes
    expected_config_entry_id, and the device is only removed if it belongs to that
    config entry.
    """
    registry = dr.async_get(hass)
    device_id = msg["device_id"]

    # A composite device id has no single underlying device to remove; reject it.
    if (
        registry.async_get(
            device_id, include_main_devices=False, include_child_devices=False
        )
        is not None
    ):
        raise HomeAssistantError("Cannot remove a composite device")
    if (
        device_entry := registry.async_get(device_id, include_composite_devices=False)
    ) is None:
        raise HomeAssistantError("Unknown device")

    if (
        expected_config_entry_id is not None
        and expected_config_entry_id != device_entry.config_entry_id
    ):
        raise HomeAssistantError("Config entry not in device")

    config_entry_id = device_entry.config_entry_id
    if (config_entry := hass.config_entries.async_get_entry(config_entry_id)) is None:
        raise HomeAssistantError("Unknown config entry")

    if not config_entry.supports_remove_device:
        raise HomeAssistantError("Config entry does not support device removal")

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

    # The integration might have removed the device already, that is fine.
    if registry.async_get(device_id):
        registry.async_remove_device(device_id)

    connection.send_message(websocket_api.result_message(msg["id"], None))


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        "type": "config/device_registry/remove",
        "device_id": str,
    }
)
@websocket_api.async_response
async def websocket_remove_device(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Remove a device."""
    await _async_remove_device(hass, connection, msg)


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
    """Remove a device.

    Deprecated alias of config/device_registry/remove. The config_entry_id
    parameter is kept for backwards compatibility and must match the device's
    config entry.
    """
    _LOGGER.warning(
        "The websocket command config/device_registry/remove_config_entry is "
        "deprecated and will be removed in Home Assistant 2027.9; use "
        "config/device_registry/remove instead"
    )
    await _async_remove_device(
        hass, connection, msg, expected_config_entry_id=msg["config_entry_id"]
    )
