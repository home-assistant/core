"""HTTP views to interact with the entity registry."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import websocket_api
from homeassistant.components.websocket_api import ERR_NOT_FOUND
from homeassistant.components.websocket_api.decorators import require_admin
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.json import json_dumps


async def async_setup(hass: HomeAssistant) -> bool:
    """Enable the Entity Registry views."""

    websocket_api.async_register_command(hass, websocket_get_entities)
    websocket_api.async_register_command(hass, websocket_get_entity)
    websocket_api.async_register_command(hass, websocket_list_entities_for_display)
    websocket_api.async_register_command(hass, websocket_list_entities)
    websocket_api.async_register_command(hass, websocket_remove_entity)
    websocket_api.async_register_command(hass, websocket_update_entity)
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
        '"success":true,"result": ['
    ).encode()
    # Concatenate cached entity registry item JSON serializations
    msg_json = (
        msg_json_prefix
        + b",".join(
            entry.partial_json_repr
            for entry in registry.entities.values()
            if entry.partial_json_repr is not None
        )
        + b"]}"
    )
    connection.send_message(msg_json)


_ENTITY_CATEGORIES_JSON = json_dumps(er.ENTITY_CATEGORY_INDEX_TO_VALUE)


@websocket_api.websocket_command(
    {vol.Required("type"): "config/entity_registry/list_for_display"}
)
@callback
def websocket_list_entities_for_display(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Handle list registry entries command."""
    registry = er.async_get(hass)
    # Build start of response message
    msg_json_prefix = (
        f'{{"id":{msg["id"]},"type":"{websocket_api.const.TYPE_RESULT}","success":true,'
        f'"result":{{"entity_categories":{_ENTITY_CATEGORIES_JSON},"entities":['
    ).encode()
    # Concatenate cached entity registry item JSON serializations
    msg_json = (
        msg_json_prefix
        + b",".join(
            entry.display_json_repr
            for entry in registry.entities.values()
            if entry.disabled_by is None and entry.display_json_repr is not None
        )
        + b"]}}"
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
        websocket_api.result_message(msg["id"], entry.extended_dict)
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
        entries[entity_id] = entry.extended_dict if entry else None

    connection.send_message(websocket_api.result_message(msg["id"], entries))


@require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "config/entity_registry/update",
        vol.Required("entity_id"): cv.entity_id,
        # If passed in, we update value. Passing None will remove old value.
        vol.Optional("aliases"): list,
        vol.Optional("area_id"): vol.Any(str, None),
        vol.Optional("device_class"): vol.Any(str, None),
        vol.Optional("icon"): vol.Any(str, None),
        vol.Optional("name"): vol.Any(str, None),
        vol.Optional("new_entity_id"): str,
        # We only allow setting disabled_by user via API.
        vol.Optional("disabled_by"): vol.Any(
            None,
            vol.All(
                vol.Coerce(er.RegistryEntryDisabler),
                er.RegistryEntryDisabler.USER.value,
            ),
        ),
        # We only allow setting hidden_by user via API.
        vol.Optional("hidden_by"): vol.Any(
            None,
            vol.All(
                vol.Coerce(er.RegistryEntryHider),
                er.RegistryEntryHider.USER.value,
            ),
        ),
        vol.Inclusive("options_domain", "entity_option"): str,
        vol.Inclusive("options", "entity_option"): vol.Any(None, dict),
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
    registry = er.async_get(hass)

    entity_id = msg["entity_id"]
    if not (entity_entry := registry.async_get(entity_id)):
        connection.send_message(
            websocket_api.error_message(msg["id"], ERR_NOT_FOUND, "Entity not found")
        )
        return

    changes = {}

    for key in (
        "area_id",
        "device_class",
        "disabled_by",
        "hidden_by",
        "icon",
        "name",
        "new_entity_id",
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
                connection.send_message(
                    websocket_api.error_message(
                        msg["id"], "invalid_info", "Device is disabled"
                    )
                )
                return

    try:
        if changes:
            entity_entry = registry.async_update_entity(entity_id, **changes)
    except ValueError as err:
        connection.send_message(
            websocket_api.error_message(msg["id"], "invalid_info", str(err))
        )
        return

    if "new_entity_id" in msg:
        entity_id = msg["new_entity_id"]

    try:
        if "options_domain" in msg:
            entity_entry = registry.async_update_entity_options(
                entity_id, msg["options_domain"], msg["options"]
            )
    except ValueError as err:
        connection.send_message(
            websocket_api.error_message(msg["id"], "invalid_info", str(err))
        )
        return

    result: dict[str, Any] = {"entity_entry": entity_entry.extended_dict}
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
    connection.send_result(msg["id"], result)


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
    registry = er.async_get(hass)

    if msg["entity_id"] not in registry.entities:
        connection.send_message(
            websocket_api.error_message(msg["id"], ERR_NOT_FOUND, "Entity not found")
        )
        return

    registry.async_remove(msg["entity_id"])
    connection.send_message(websocket_api.result_message(msg["id"]))
