"""Websocket API for the Sandbox integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import Unauthorized
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import DATA_SANDBOX


def _require_sandbox_token(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
) -> str:
    """Validate the connection uses a sandbox token. Return the sandbox_id."""
    sandbox_data = hass.data[DATA_SANDBOX]
    token_id = connection.refresh_token_id
    if token_id is None or token_id not in sandbox_data.token_to_sandbox:
        raise Unauthorized
    return sandbox_data.token_to_sandbox[token_id]


@callback
def async_setup(hass: HomeAssistant) -> None:
    """Register sandbox websocket commands."""
    websocket_api.async_register_command(hass, ws_get_entries)
    websocket_api.async_register_command(hass, ws_update_entry)
    websocket_api.async_register_command(hass, ws_register_device)
    websocket_api.async_register_command(hass, ws_update_device)
    websocket_api.async_register_command(hass, ws_remove_device)
    websocket_api.async_register_command(hass, ws_register_entity)
    websocket_api.async_register_command(hass, ws_update_entity)
    websocket_api.async_register_command(hass, ws_remove_entity)
    websocket_api.async_register_command(hass, ws_update_state)
    websocket_api.async_register_command(hass, ws_subscribe_service_calls)
    websocket_api.async_register_command(hass, ws_subscribe_entity_commands)
    websocket_api.async_register_command(hass, ws_entity_command_result)


@websocket_api.websocket_command(
    {vol.Required("type"): "sandbox/get_entries"}
)
@callback
def ws_get_entries(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return config entries assigned to this sandbox token."""
    sandbox_id = _require_sandbox_token(hass, connection)
    sandbox_data = hass.data[DATA_SANDBOX]
    sandbox_info = sandbox_data.sandboxes[sandbox_id]

    entries = []
    for entry_config in sandbox_info.entries:
        entries.append(
            {
                "entry_id": entry_config["entry_id"],
                "domain": entry_config["domain"],
                "title": entry_config.get("title", entry_config["domain"]),
                "data": entry_config.get("data", {}),
                "options": entry_config.get("options", {}),
            }
        )

    connection.send_result(msg["id"], entries)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "sandbox/update_entry",
        vol.Required("sandbox_entry_id"): str,
        vol.Optional("data"): dict,
        vol.Optional("options"): dict,
        vol.Optional("title"): str,
    }
)
@callback
def ws_update_entry(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Update a sandbox config entry's stored data."""
    sandbox_id = _require_sandbox_token(hass, connection)
    sandbox_data = hass.data[DATA_SANDBOX]
    sandbox_info = sandbox_data.sandboxes[sandbox_id]

    sandbox_entry_id = msg["sandbox_entry_id"]
    entry_config = next(
        (e for e in sandbox_info.entries if e["entry_id"] == sandbox_entry_id),
        None,
    )
    if entry_config is None:
        connection.send_error(
            msg["id"], "not_found", "Entry not assigned to this sandbox"
        )
        return

    if "data" in msg:
        entry_config["data"] = msg["data"]
    if "options" in msg:
        entry_config["options"] = msg["options"]
    if "title" in msg:
        entry_config["title"] = msg["title"]

    connection.send_result(msg["id"])


@websocket_api.websocket_command(
    {
        vol.Required("type"): "sandbox/register_device",
        vol.Required("sandbox_entry_id"): str,
        vol.Required("identifiers"): vol.All(
            [{vol.Required("domain"): str, vol.Required("id"): str}],
            vol.Length(min=1),
        ),
        vol.Optional("name"): str,
        vol.Optional("manufacturer"): str,
        vol.Optional("model"): str,
        vol.Optional("sw_version"): str,
        vol.Optional("hw_version"): str,
        vol.Optional("entry_type"): str,
    }
)
@websocket_api.async_response
async def ws_register_device(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Register a device in HA Core on behalf of a sandbox."""
    sandbox_id = _require_sandbox_token(hass, connection)
    sandbox_data = hass.data[DATA_SANDBOX]
    sandbox_info = sandbox_data.sandboxes[sandbox_id]

    sandbox_entry_id = msg["sandbox_entry_id"]
    if not any(e["entry_id"] == sandbox_entry_id for e in sandbox_info.entries):
        connection.send_error(
            msg["id"], "not_found", "Entry not assigned to this sandbox"
        )
        return

    host_entry_id = sandbox_data.get_host_entry_id(sandbox_id)
    if host_entry_id is None:
        connection.send_error(
            msg["id"], "not_found", "No host config entry for sandbox"
        )
        return

    identifiers = {(i["domain"], i["id"]) for i in msg["identifiers"]}

    device_reg = dr.async_get(hass)
    kwargs: dict[str, Any] = {
        "config_entry_id": host_entry_id,
        "identifiers": identifiers,
    }
    for key in ("name", "manufacturer", "model", "sw_version", "hw_version"):
        if key in msg:
            kwargs[key] = msg[key]
    if "entry_type" in msg:
        kwargs["entry_type"] = dr.DeviceEntryType(msg["entry_type"])

    device = device_reg.async_get_or_create(**kwargs)

    connection.send_result(msg["id"], {"device_id": device.id})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "sandbox/update_device",
        vol.Required("device_id"): str,
        vol.Optional("name"): str,
        vol.Optional("manufacturer"): str,
        vol.Optional("model"): str,
        vol.Optional("sw_version"): str,
        vol.Optional("hw_version"): str,
        vol.Optional("name_by_user"): vol.Any(str, None),
        vol.Optional("disabled_by"): vol.Any(str, None),
    }
)
@websocket_api.async_response
async def ws_update_device(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Update a device in HA Core on behalf of a sandbox."""
    _require_sandbox_token(hass, connection)

    device_reg = dr.async_get(hass)
    device = device_reg.async_get(msg["device_id"])
    if device is None:
        connection.send_error(msg["id"], "not_found", "Device not found")
        return

    kwargs: dict[str, Any] = {}
    for key in ("name", "manufacturer", "model", "sw_version", "hw_version", "name_by_user"):
        if key in msg:
            kwargs[key] = msg[key]
    if "disabled_by" in msg:
        kwargs["disabled_by"] = (
            dr.DeviceEntryDisabler(msg["disabled_by"])
            if msg["disabled_by"]
            else None
        )

    device_reg.async_update_device(device.id, **kwargs)
    connection.send_result(msg["id"])


@websocket_api.websocket_command(
    {
        vol.Required("type"): "sandbox/remove_device",
        vol.Required("device_id"): str,
    }
)
@websocket_api.async_response
async def ws_remove_device(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Remove a device from HA Core on behalf of a sandbox."""
    sandbox_id = _require_sandbox_token(hass, connection)
    sandbox_data = hass.data[DATA_SANDBOX]
    host_entry_id = sandbox_data.get_host_entry_id(sandbox_id)

    device_reg = dr.async_get(hass)
    device = device_reg.async_get(msg["device_id"])
    if device is None:
        connection.send_error(msg["id"], "not_found", "Device not found")
        return

    device_reg.async_remove_device(device.id)
    connection.send_result(msg["id"])


@websocket_api.websocket_command(
    {
        vol.Required("type"): "sandbox/register_entity",
        vol.Required("sandbox_entry_id"): str,
        vol.Required("domain"): str,
        vol.Required("platform"): str,
        vol.Required("unique_id"): str,
        vol.Optional("device_id"): str,
        vol.Optional("original_name"): str,
        vol.Optional("original_icon"): str,
        vol.Optional("entity_category"): str,
        vol.Optional("suggested_object_id"): str,
        vol.Optional("capabilities"): dict,
        vol.Optional("supported_features"): int,
        vol.Optional("has_entity_name"): bool,
    }
)
@websocket_api.async_response
async def ws_register_entity(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Register an entity in HA Core on behalf of a sandbox."""
    sandbox_id = _require_sandbox_token(hass, connection)
    sandbox_data = hass.data[DATA_SANDBOX]
    sandbox_info = sandbox_data.sandboxes[sandbox_id]

    sandbox_entry_id = msg["sandbox_entry_id"]
    if not any(e["entry_id"] == sandbox_entry_id for e in sandbox_info.entries):
        connection.send_error(
            msg["id"], "not_found", "Entry not assigned to this sandbox"
        )
        return

    host_entry_id = sandbox_data.get_host_entry_id(sandbox_id)
    host_entry = hass.config_entries.async_get_entry(host_entry_id) if host_entry_id else None
    if host_entry is None:
        connection.send_error(
            msg["id"], "not_found", "No host config entry for sandbox"
        )
        return

    domain = msg["domain"]
    manager = sandbox_data.entity_managers.get(sandbox_id)
    if manager is None:
        connection.send_error(msg["id"], "not_found", "No entity manager")
        return

    if domain not in manager._platform_add_callbacks:
        await hass.config_entries.async_forward_entry_setups(
            host_entry, [domain]
        )

    from .entity import SandboxEntityDescription

    description = SandboxEntityDescription(
        domain=domain,
        platform=msg["platform"],
        unique_id=f"{sandbox_id}_{msg['unique_id']}",
        sandbox_id=sandbox_id,
        sandbox_entry_id=sandbox_entry_id,
        device_id=msg.get("device_id"),
        original_name=msg.get("original_name"),
        original_icon=msg.get("original_icon"),
        entity_category=msg.get("entity_category"),
        supported_features=msg.get("supported_features", 0),
        capabilities=msg.get("capabilities", {}),
        has_entity_name=msg.get("has_entity_name", False),
    )

    entity = manager.add_entity(description)

    add_entities = manager._platform_add_callbacks.get(domain)
    if add_entities is None:
        connection.send_error(
            msg["id"], "not_ready", f"Platform {domain} not ready"
        )
        return

    add_entities([entity])

    connection.send_result(
        msg["id"],
        {"entity_id": entity.entity_id or ""},
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): "sandbox/update_entity",
        vol.Required("entity_id"): str,
        vol.Optional("name"): vol.Any(str, None),
        vol.Optional("icon"): vol.Any(str, None),
        vol.Optional("disabled_by"): vol.Any(str, None),
        vol.Optional("hidden_by"): vol.Any(str, None),
        vol.Optional("original_name"): vol.Any(str, None),
        vol.Optional("original_icon"): vol.Any(str, None),
        vol.Optional("capabilities"): vol.Any(dict, None),
        vol.Optional("supported_features"): int,
        vol.Optional("device_id"): vol.Any(str, None),
    }
)
@websocket_api.async_response
async def ws_update_entity(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Update an entity registry entry in HA Core on behalf of a sandbox."""
    _require_sandbox_token(hass, connection)

    entity_reg = er.async_get(hass)
    entity_entry = entity_reg.async_get(msg["entity_id"])
    if entity_entry is None:
        connection.send_error(msg["id"], "not_found", "Entity not found")
        return

    kwargs: dict[str, Any] = {}
    for key in (
        "name",
        "icon",
        "original_name",
        "original_icon",
        "capabilities",
        "supported_features",
        "device_id",
    ):
        if key in msg:
            kwargs[key] = msg[key]

    if "disabled_by" in msg:
        kwargs["disabled_by"] = (
            er.RegistryEntryDisabler(msg["disabled_by"])
            if msg["disabled_by"]
            else None
        )
    if "hidden_by" in msg:
        kwargs["hidden_by"] = (
            er.RegistryEntryHider(msg["hidden_by"])
            if msg["hidden_by"]
            else None
        )

    entity_reg.async_update_entity(msg["entity_id"], **kwargs)
    connection.send_result(msg["id"])


@websocket_api.websocket_command(
    {
        vol.Required("type"): "sandbox/update_state",
        vol.Required("entity_id"): str,
        vol.Required("state"): str,
        vol.Optional("attributes"): dict,
    }
)
@callback
def ws_update_state(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Update an entity state in HA Core from a sandbox."""
    sandbox_id = _require_sandbox_token(hass, connection)
    sandbox_data = hass.data[DATA_SANDBOX]

    manager = sandbox_data.entity_managers.get(sandbox_id)
    if manager is not None:
        entity = manager.get_entity(msg["entity_id"])
        if entity is not None:
            entity.sandbox_update_state(msg["state"], msg.get("attributes") or {})
            connection.send_result(msg["id"])
            return

    hass.states.async_set(
        msg["entity_id"],
        msg["state"],
        msg.get("attributes"),
    )
    connection.send_result(msg["id"])


@websocket_api.websocket_command(
    {
        vol.Required("type"): "sandbox/remove_entity",
        vol.Required("entity_id"): str,
    }
)
@callback
def ws_remove_entity(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Remove a sandbox entity from HA Core."""
    _require_sandbox_token(hass, connection)

    entity_reg = er.async_get(hass)
    entity_entry = entity_reg.async_get(msg["entity_id"])
    if entity_entry and entity_entry.platform == "sandbox":
        entity_reg.async_remove(msg["entity_id"])

    hass.states.async_remove(msg["entity_id"])
    connection.send_result(msg["id"])


@websocket_api.websocket_command(
    {
        vol.Required("type"): "sandbox/subscribe_service_calls",
        vol.Required("entity_ids"): [str],
    }
)
@callback
def ws_subscribe_service_calls(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Subscribe to service calls targeting sandbox entities.

    Forwards service calls for the specified entity IDs to the sandbox client.
    """
    _require_sandbox_token(hass, connection)

    entity_ids = set(msg["entity_ids"])
    sandbox_data = hass.data[DATA_SANDBOX]
    sandbox_id = sandbox_data.token_to_sandbox[connection.refresh_token_id]

    managed_entities = sandbox_data.sandboxes[sandbox_id].managed_entity_ids
    managed_entities.update(entity_ids)

    from homeassistant.const import EVENT_CALL_SERVICE

    @callback
    def forward_service_call(event: Any) -> None:
        """Forward service calls targeting sandbox entities."""
        service_data = dict(event.data.get("service_data", {}))
        target_entity_ids = set()

        if "entity_id" in service_data:
            target = service_data["entity_id"]
            if isinstance(target, str):
                target_entity_ids.add(target)
            elif isinstance(target, list):
                target_entity_ids.update(target)

        matching = target_entity_ids & entity_ids
        if not matching:
            return

        connection.send_message(
            websocket_api.event_message(
                msg["id"],
                {
                    "domain": event.data.get("domain"),
                    "service": event.data.get("service"),
                    "service_data": service_data,
                    "entity_ids": list(matching),
                },
            )
        )

    unsub = hass.bus.async_listen(EVENT_CALL_SERVICE, forward_service_call)
    connection.subscriptions[msg["id"]] = unsub
    connection.send_result(msg["id"])


@websocket_api.websocket_command(
    {vol.Required("type"): "sandbox/subscribe_entity_commands"}
)
@callback
def ws_subscribe_entity_commands(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Subscribe to entity method calls from the host.

    The host pushes commands as subscription events when proxy entities
    need to forward method calls to the sandbox. The sandbox responds
    with sandbox/entity_command_result.
    """
    sandbox_id = _require_sandbox_token(hass, connection)
    sandbox_data = hass.data[DATA_SANDBOX]
    sandbox_info = sandbox_data.sandboxes.get(sandbox_id)
    if sandbox_info is None:
        connection.send_error(msg["id"], "not_found", "Sandbox not found")
        return

    @callback
    def send_command(command: dict[str, Any]) -> None:
        """Send a command to the sandbox."""
        connection.send_message(
            websocket_api.event_message(msg["id"], command)
        )

    sandbox_info.send_command = send_command

    @callback
    def unsub() -> None:
        sandbox_info.send_command = None

    connection.subscriptions[msg["id"]] = unsub
    connection.send_result(msg["id"])


@websocket_api.websocket_command(
    {
        vol.Required("type"): "sandbox/entity_command_result",
        vol.Required("call_id"): str,
        vol.Required("success"): bool,
        vol.Optional("result"): vol.Any(dict, list, str, int, float, bool, None),
        vol.Optional("error"): str,
    }
)
@callback
def ws_entity_command_result(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Receive the result of a forwarded entity method call."""
    sandbox_id = _require_sandbox_token(hass, connection)
    sandbox_data = hass.data[DATA_SANDBOX]

    from .entity import SandboxEntityManager

    manager = sandbox_data.entity_managers.get(sandbox_id)
    if manager is None:
        connection.send_error(msg["id"], "not_found", "No entity manager")
        return

    error = msg.get("error") if not msg["success"] else None
    manager.resolve_call(msg["call_id"], msg.get("result"), error)
    connection.send_result(msg["id"])
