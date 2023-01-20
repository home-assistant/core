"""HTTP views to interact with the entity registry."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.auth.permissions.const import CAT_ENTITIES, POLICY_EDIT
from homeassistant.components import websocket_api
from homeassistant.components.websocket_api import ERR_NOT_FOUND
from homeassistant.components.websocket_api.decorators import require_admin
from homeassistant.const import (
    ATTR_AREA_ID,
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    ATTR_ICON,
    ATTR_NAME,
)
import homeassistant.core as ha
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import NoEntitySpecifiedError, Unauthorized, UnknownUser
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)

DOMAIN = "config"

ATTR_ALIASES = "aliases"
ATTR_AREA = "area"
ATTR_DISABLED = "disabled"
ATTR_DISABLED_BY = "disabled_by"
ATTR_HIDDEN = "hidden"
ATTR_HIDDEN_BY = "hidden_by"
ATTR_OPTIONS = "options"
ATTR_OPTIONS_DOMAIN = "options_domain"
ATTR_NEW_ENTITY_ID = "new_entity_id"
SERVICE_UPDATE_ENTITY = "update_entity"
SERVICE_REMOVE_ENTITY = "remove_entity"

SCHEMA_UPDATE_ENTITY_COMMON = {
    vol.Required(ATTR_ENTITY_ID): cv.entity_id,
    # If passed in, we update value. Passing None will remove old value.
    vol.Optional(ATTR_ALIASES): vol.All(cv.ensure_list, [str]),
    vol.Optional(ATTR_AREA_ID): vol.Any(str, None),
    vol.Optional(ATTR_DEVICE_CLASS): vol.Any(str, None),
    vol.Optional(ATTR_ICON): vol.Any(str, None),
    vol.Optional(ATTR_NAME): vol.Any(str, None),
    vol.Optional(ATTR_NEW_ENTITY_ID): str,
    vol.Inclusive(ATTR_OPTIONS_DOMAIN, "entity_option"): str,
    vol.Inclusive(ATTR_OPTIONS, "entity_option"): vol.Any(None, dict),
}
SCHEMA_UPDATE_ENTITY = vol.Schema(
    {
        **SCHEMA_UPDATE_ENTITY_COMMON,
        vol.Optional(ATTR_DISABLED): vol.Any(bool, None),
        vol.Optional(ATTR_HIDDEN): vol.Any(bool, None),
    }
)

SCHEMA_REMOVE_ENTITY = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
    }
)


async def async_setup(hass: HomeAssistant) -> bool:
    """Enable the Entity Registry views."""

    websocket_api.async_register_command(hass, websocket_list_entities)
    websocket_api.async_register_command(hass, websocket_get_entity)
    websocket_api.async_register_command(hass, websocket_get_entities)
    websocket_api.async_register_command(hass, websocket_update_entity)
    websocket_api.async_register_command(hass, websocket_remove_entity)

    async def async_handle_update_entity_service(call: ha.ServiceCall) -> None:
        """Service handler for updating an entity."""
        if call.context.user_id:
            user = await hass.auth.async_get_user(call.context.user_id)

            if user is None:
                raise UnknownUser(
                    context=call.context,
                    permission=POLICY_EDIT,
                    user_id=call.context.user_id,
                )

            if not user.permissions.check_entity(
                call.data[ATTR_ENTITY_ID], POLICY_EDIT
            ):
                raise Unauthorized(
                    context=call.context,
                    permission=POLICY_EDIT,
                    user_id=call.context.user_id,
                    perm_category=CAT_ENTITIES,
                )

        data = dict(call.data)

        disabled = data.get(ATTR_DISABLED)
        if disabled is not None:
            data[ATTR_DISABLED_BY] = er.RegistryEntryDisabler.USER if disabled else None
            del data[ATTR_DISABLED]

        hidden = data.get(ATTR_HIDDEN)
        if hidden is not None:
            data[ATTR_HIDDEN_BY] = er.RegistryEntryHider.USER if hidden else None
            del data[ATTR_HIDDEN]

        update_entity(hass, data)

    hass.services.async_register(
        DOMAIN,
        SERVICE_UPDATE_ENTITY,
        async_handle_update_entity_service,
        schema=SCHEMA_UPDATE_ENTITY,
    )

    async def async_handle_remove_entity_service(call: ha.ServiceCall) -> None:
        """Service handler for removing an entity."""
        entity_ids = call.data[ATTR_ENTITY_ID]
        if call.context.user_id:
            user = await hass.auth.async_get_user(call.context.user_id)

            if user is None:
                raise UnknownUser(
                    context=call.context,
                    permission=POLICY_EDIT,
                    user_id=call.context.user_id,
                )

            for entity_id in entity_ids:
                if not user.permissions.check_entity(entity_id, POLICY_EDIT):
                    raise Unauthorized(
                        context=call.context,
                        permission=POLICY_EDIT,
                        user_id=call.context.user_id,
                        perm_category=CAT_ENTITIES,
                    )

        for entity_id in entity_ids:
            remove_entity(hass, entity_id)

    hass.services.async_register(
        DOMAIN,
        SERVICE_REMOVE_ENTITY,
        async_handle_remove_entity_service,
        schema=SCHEMA_REMOVE_ENTITY,
    )

    return True


@websocket_api.websocket_command({vol.Required("type"): "config/entity_registry/list"})
@callback
def websocket_list_entities(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Handle list registry entries command."""
    registry = er.async_get(hass)
    # Build start of response message
    msg_json_prefix = (
        f'{{"id":{msg["id"]},"type": "{websocket_api.const.TYPE_RESULT}",'
        f'"success":true,"result": ['
    )
    # Concatenate cached entity registry item JSON serializations
    msg_json = (
        msg_json_prefix
        + ",".join(
            entry.partial_json_repr
            for entry in registry.entities.values()
            if entry.partial_json_repr is not None
        )
        + "]}"
    )
    connection.send_message(msg_json)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "config/entity_registry/get",
        vol.Required("entity_id"): cv.entity_id,
    }
)
@callback
def websocket_get_entity(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Handle get entity registry entry command.

    Async friendly.
    """
    registry = er.async_get(hass)

    if (entry := registry.entities.get(msg["entity_id"])) is None:
        connection.send_message(
            websocket_api.error_message(msg["id"], ERR_NOT_FOUND, "Entity not found")
        )
        return

    connection.send_message(
        websocket_api.result_message(msg["id"], _entry_ext_dict(entry))
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): "config/entity_registry/get_entries",
        vol.Required("entity_ids"): cv.entity_ids,
    }
)
@callback
def websocket_get_entities(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Handle get entity registry entries command.

    Async friendly.
    """
    registry = er.async_get(hass)

    entity_ids = msg["entity_ids"]
    entries: dict[str, dict[str, Any] | None] = {}
    for entity_id in entity_ids:
        entry = registry.entities.get(entity_id)
        entries[entity_id] = _entry_ext_dict(entry) if entry else None

    connection.send_message(websocket_api.result_message(msg["id"], entries))


@require_admin
@websocket_api.websocket_command(
    {
        **SCHEMA_UPDATE_ENTITY_COMMON,
        vol.Required("type"): "config/entity_registry/update",
        # We only allow setting disabled_by user via API.
        vol.Optional(ATTR_DISABLED_BY): vol.Any(
            None,
            vol.All(
                vol.Coerce(er.RegistryEntryDisabler),
                er.RegistryEntryDisabler.USER.value,
            ),
        ),
        # We only allow setting hidden_by user via API.
        vol.Optional(ATTR_HIDDEN_BY): vol.Any(
            None,
            vol.All(
                vol.Coerce(er.RegistryEntryHider),
                er.RegistryEntryHider.USER.value,
            ),
        ),
    }
)
@callback
def websocket_update_entity(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Handle update entity websocket command.

    Async friendly.
    """
    try:
        result = update_entity(hass, msg)
        connection.send_result(msg["id"], result)
    except NoEntitySpecifiedError as err:
        connection.send_message(
            websocket_api.error_message(msg["id"], ERR_NOT_FOUND, str(err))
        )
    except ValueError as err:
        connection.send_message(
            websocket_api.error_message(msg["id"], "invalid_info", str(err))
        )


def update_entity(
    hass: HomeAssistant,
    msg: dict[str, Any],
) -> dict[str, Any]:
    """Handle update entity."""
    registry = er.async_get(hass)

    entity_id = msg["entity_id"]
    if not (entity_entry := registry.async_get(entity_id)):
        raise NoEntitySpecifiedError(f"Entity {entity_id} not found")

    changes = {}

    for key in (
        ATTR_AREA_ID,
        ATTR_DEVICE_CLASS,
        ATTR_DISABLED_BY,
        ATTR_HIDDEN_BY,
        ATTR_ICON,
        ATTR_NAME,
        ATTR_NEW_ENTITY_ID,
    ):
        if key in msg:
            changes[key] = msg[key]

    if "aliases" in msg:
        # Convert aliases to a set
        changes["aliases"] = set(msg["aliases"])

    if "disabled_by" in msg and msg["disabled_by"] is None:
        # Don't allow enabling an entity of a disabled device
        if entity_entry.device_id:
            device_registry = dr.async_get(hass)
            device = device_registry.async_get(entity_entry.device_id)
            if device and device.disabled:
                raise ValueError("Device is disabled")

    if changes:
        entity_entry = registry.async_update_entity(entity_id, **changes)

    if "new_entity_id" in msg:
        entity_id = msg["new_entity_id"]

    if ATTR_OPTIONS_DOMAIN in msg:
        entity_entry = registry.async_update_entity_options(
            entity_id, msg[ATTR_OPTIONS_DOMAIN], msg[ATTR_OPTIONS]
        )

    result: dict[str, Any] = {"entity_entry": _entry_ext_dict(entity_entry)}
    if "disabled_by" in changes and changes["disabled_by"] is None:
        # Enabling an entity requires a config entry reload, or HA restart
        if (
            not (config_entry_id := entity_entry.config_entry_id)
            or (config_entry := hass.config_entries.async_get_entry(config_entry_id))
            and not config_entry.supports_unload
        ):
            result["require_restart"] = True
        else:
            result["reload_delay"] = config_entries.RELOAD_AFTER_UPDATE_DELAY
    return result


@require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "config/entity_registry/remove",
        vol.Required("entity_id"): cv.entity_id,
    }
)
@callback
def websocket_remove_entity(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Handle remove entity websocket command.

    Async friendly.
    """
    try:
        remove_entity(hass, msg["entity_id"])
        connection.send_message(websocket_api.result_message(msg["id"]))
    except NoEntitySpecifiedError as err:
        connection.send_message(
            websocket_api.error_message(msg["id"], ERR_NOT_FOUND, str(err))
        )


def remove_entity(
    hass: HomeAssistant,
    entity_id: str,
) -> None:
    """Handle remove entity."""
    registry = er.async_get(hass)

    if entity_id not in registry.entities:
        raise NoEntitySpecifiedError(f"Entity {entity_id} not found")

    registry.async_remove(entity_id)


@callback
def _entry_ext_dict(entry: er.RegistryEntry) -> dict[str, Any]:
    """Convert entry to API format."""
    data = entry.as_partial_dict
    data["aliases"] = entry.aliases
    data["capabilities"] = entry.capabilities
    data["device_class"] = entry.device_class
    data["options"] = entry.options
    data["original_device_class"] = entry.original_device_class
    data["original_icon"] = entry.original_icon
    return data
