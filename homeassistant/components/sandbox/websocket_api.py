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
    websocket_api.async_register_command(hass, ws_register_service)
    websocket_api.async_register_command(hass, ws_sandbox_call_service)
    websocket_api.async_register_command(hass, ws_service_call_result)
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
        vol.Optional("device_class"): str,
        vol.Optional("state_class"): str,
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

    from .entity import SandboxEntityDescription
    from .host_platform import async_get_or_create_host_platform

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
        device_class=msg.get("device_class"),
        state_class=msg.get("state_class"),
        supported_features=msg.get("supported_features", 0),
        capabilities=msg.get("capabilities", {}),
        has_entity_name=msg.get("has_entity_name", False),
    )

    platform = async_get_or_create_host_platform(
        hass, domain, host_entry, manager
    )

    entity = await platform.async_add_proxy_entity(description)

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
        vol.Required("type"): "sandbox/register_service",
        vol.Required("domain"): str,
        vol.Required("service"): str,
    }
)
@callback
def ws_register_service(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Register a service on the host on behalf of a sandbox.

    If the service already exists (e.g. entity component loaded it),
    this is a no-op. Otherwise a proxy service is created that forwards
    calls to the sandbox for execution.
    """
    import asyncio

    sandbox_id = _require_sandbox_token(hass, connection)
    sandbox_data = hass.data[DATA_SANDBOX]

    domain = msg["domain"]
    service = msg["service"]

    if hass.services.has_service(domain, service):
        connection.send_result(msg["id"])
        return

    sandbox_info = sandbox_data.sandboxes[sandbox_id]

    async def proxy_service_handler(call: Any) -> Any:
        """Forward service call to sandbox for execution."""
        if sandbox_info.send_command is None:
            from homeassistant.exceptions import ServiceNotFound

            raise ServiceNotFound(domain, service)

        call_id = f"svc_{sandbox_id}_{id(call)}"
        future: asyncio.Future[Any] = hass.loop.create_future()
        sandbox_info.pending_service_calls[call_id] = future

        target: dict[str, Any] = {}
        if hasattr(call, "target") and call.target:
            target = dict(call.target)

        # Use pending_contexts if sandbox/call_service stored one for
        # this context. This ensures only contexts originating from the
        # sandbox client are forwarded — not the auto-generated context
        # from the standard call_service WS command.
        context_data: dict[str, str | None] | None = None
        if call.context:
            context_data = sandbox_info.pending_contexts.pop(
                call.context.id, None
            )

        sandbox_info.send_command(
            {
                "type": "call_service",
                "call_id": call_id,
                "domain": call.domain,
                "service": call.service,
                "service_data": dict(call.data),
                "target": target,
                "return_response": call.return_response,
                "context": context_data,
            }
        )

        try:
            return await asyncio.wait_for(future, timeout=30)
        except asyncio.TimeoutError:
            sandbox_info.pending_service_calls.pop(call_id, None)
            raise

    from homeassistant.core import SupportsResponse

    hass.services.async_register(
        domain, service, proxy_service_handler,
        supports_response=SupportsResponse.OPTIONAL,
    )
    connection.send_result(msg["id"])


@websocket_api.websocket_command(
    {
        vol.Required("type"): "sandbox/call_service",
        vol.Required("domain"): str,
        vol.Required("service"): str,
        vol.Optional("service_data"): dict,
        vol.Optional("target"): vol.Any(dict, None),
        vol.Optional("return_response"): bool,
        vol.Optional("context"): dict,
    }
)
@websocket_api.async_response
async def ws_sandbox_call_service(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Call a service with full context forwarding.

    Unlike the standard call_service WS command which creates context from the
    connection, this uses the context passed from the sandbox so that permission
    checks and context tracking work correctly.
    """
    import voluptuous as _vol

    from homeassistant.components.websocket_api import const
    from homeassistant.core import Context
    from homeassistant.exceptions import (
        HomeAssistantError,
        ServiceNotFound,
        ServiceValidationError,
    )

    sandbox_id = _require_sandbox_token(hass, connection)
    sandbox_data = hass.data[DATA_SANDBOX]
    sandbox_info = sandbox_data.sandboxes[sandbox_id]

    domain = msg["domain"]
    service = msg["service"]
    service_data = msg.get("service_data") or {}
    target = msg.get("target")
    return_response = msg.get("return_response", False)

    # Reconstruct context from sandbox
    context_data = msg.get("context")
    if context_data:
        context = Context(
            id=context_data.get("id"),
            user_id=context_data.get("user_id"),
            parent_id=context_data.get("parent_id"),
        )
        # Store context so the proxy_service_handler can forward it
        # to the sandbox. Only contexts explicitly sent by the sandbox
        # client are forwarded — not auto-generated ones from standard
        # call_service.
        sandbox_info.pending_contexts[context.id] = {
            "id": context.id,
            "user_id": context.user_id,
            "parent_id": context.parent_id,
        }
    else:
        context = connection.context(msg)

    try:
        response = await hass.services.async_call(
            domain,
            service,
            service_data,
            blocking=True,
            context=context,
            target=target,
            return_response=return_response,
        )
        result: dict[str, Any] = {"context": context.as_dict()}
        if return_response:
            result["response"] = response
        connection.send_result(msg["id"], result)
    except ServiceNotFound as err:
        connection.send_error(
            msg["id"],
            const.ERR_NOT_FOUND,
            f"Service {err.domain}.{err.service} not found.",
            translation_domain=err.translation_domain,
            translation_key=err.translation_key,
            translation_placeholders=err.translation_placeholders,
        )
    except _vol.Invalid as err:
        connection.send_error(msg["id"], const.ERR_INVALID_FORMAT, str(err))
    except ServiceValidationError as err:
        connection.send_error(
            msg["id"],
            const.ERR_SERVICE_VALIDATION_ERROR,
            f"Validation error: {err}",
            translation_domain=err.translation_domain,
            translation_key=err.translation_key,
            translation_placeholders=err.translation_placeholders,
        )
    except Unauthorized:
        connection.send_error(msg["id"], const.ERR_UNAUTHORIZED, "Unauthorized")
    except HomeAssistantError as err:
        connection.send_error(
            msg["id"],
            const.ERR_HOME_ASSISTANT_ERROR,
            str(err),
            translation_domain=err.translation_domain,
            translation_key=err.translation_key,
            translation_placeholders=err.translation_placeholders,
        )
    except Exception as err:
        connection.logger.exception("Unexpected exception in sandbox/call_service")
        connection.send_error(msg["id"], const.ERR_UNKNOWN_ERROR, str(err))


@websocket_api.websocket_command(
    {
        vol.Required("type"): "sandbox/service_call_result",
        vol.Required("call_id"): str,
        vol.Required("success"): bool,
        vol.Optional("result"): vol.Any(dict, list, str, int, float, bool, None),
        vol.Optional("error"): str,
        vol.Optional("error_type"): str,
        vol.Optional("translation_domain"): str,
        vol.Optional("translation_key"): str,
        vol.Optional("translation_placeholders"): dict,
    }
)
@callback
def ws_service_call_result(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Receive the result of a forwarded service call from the sandbox."""
    import voluptuous as _vol

    from homeassistant.exceptions import (
        HomeAssistantError,
        ServiceNotSupported,
        ServiceValidationError,
        Unauthorized,
    )

    sandbox_id = _require_sandbox_token(hass, connection)
    sandbox_data = hass.data[DATA_SANDBOX]
    sandbox_info = sandbox_data.sandboxes.get(sandbox_id)

    if sandbox_info is None:
        connection.send_error(msg["id"], "not_found", "Sandbox not found")
        return

    future = sandbox_info.pending_service_calls.pop(msg["call_id"], None)
    if future is None or future.done():
        connection.send_result(msg["id"])
        return

    if msg["success"]:
        future.set_result(msg.get("result"))
    else:
        error_msg = msg.get("error", "Unknown error")
        error_type = msg.get("error_type", "")
        translation_domain = msg.get("translation_domain")
        translation_key = msg.get("translation_key")
        translation_placeholders = msg.get("translation_placeholders")

        if error_type == "Unauthorized":
            exc: Exception = Unauthorized()
        elif error_type == "Invalid":
            exc = _vol.Invalid(error_msg)
        elif error_type == "MultipleInvalid":
            exc = _vol.MultipleInvalid([_vol.Invalid(error_msg)])
        elif error_type == "ServiceNotSupported":
            placeholders = translation_placeholders or {}
            domain = placeholders.get("domain", "")
            service = placeholders.get("service", "")
            entity_id = placeholders.get("entity_id", "")
            exc = ServiceNotSupported(domain, service, entity_id)
        elif error_type == "ServiceValidationError":
            if translation_domain and translation_key:
                exc = ServiceValidationError(
                    translation_domain=translation_domain,
                    translation_key=translation_key,
                    translation_placeholders=translation_placeholders,
                )
            else:
                exc = ServiceValidationError(error_msg)
        elif error_type == "HomeAssistantError" or not error_type:
            if translation_domain and translation_key:
                exc = HomeAssistantError(
                    translation_domain=translation_domain,
                    translation_key=translation_key,
                    translation_placeholders=translation_placeholders,
                )
            else:
                exc = HomeAssistantError(error_msg)
        else:
            # Unknown error types — use ServiceValidationError if it looks
            # like a validation error subclass, otherwise HomeAssistantError
            if translation_domain and translation_key:
                exc = ServiceValidationError(
                    translation_domain=translation_domain,
                    translation_key=translation_key,
                    translation_placeholders=translation_placeholders,
                )
            else:
                exc = HomeAssistantError(error_msg)
        future.set_exception(exc)

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
