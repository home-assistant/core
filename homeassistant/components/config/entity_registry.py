"""HTTP views to interact with the entity registry."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import websocket_api
from homeassistant.components.websocket_api import ERR_NOT_FOUND
from homeassistant.components.websocket_api.decorators import require_admin
from homeassistant.components.websocket_api.messages import (
    IDEN_JSON_TEMPLATE,
    IDEN_TEMPLATE,
    message_to_json,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)


async def async_setup(hass: HomeAssistant) -> bool:
    """Enable the Entity Registry views."""

    cached_list_entities: str | None = None

    @callback
    def _async_clear_list_entities_cache(event: Event) -> None:
        nonlocal cached_list_entities
        cached_list_entities = None

    @websocket_api.websocket_command(
        {vol.Required("type"): "config/entity_registry/list"}
    )
    @callback
    def websocket_list_entities(
        hass: HomeAssistant,
        connection: websocket_api.ActiveConnection,
        msg: dict[str, Any],
    ) -> None:
        """Handle list registry entries command."""
        nonlocal cached_list_entities
        if not cached_list_entities:
            registry = er.async_get(hass)
            cached_list_entities = message_to_json(
                websocket_api.result_message(
                    IDEN_TEMPLATE,  # type: ignore[arg-type]
                    [_entry_dict(entry) for entry in registry.entities.values()],
                )
            )
        connection.send_message(
            cached_list_entities.replace(IDEN_JSON_TEMPLATE, str(msg["id"]), 1)
        )

    hass.bus.async_listen(
        er.EVENT_ENTITY_REGISTRY_UPDATED,
        _async_clear_list_entities_cache,
        run_immediately=True,
    )
    websocket_api.async_register_command(hass, websocket_list_entities)
    websocket_api.async_register_command(hass, websocket_get_entity)
    websocket_api.async_register_command(hass, websocket_update_entity)
    websocket_api.async_register_command(hass, websocket_remove_entity)
    return True


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


@require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "config/entity_registry/update",
        vol.Required("entity_id"): cv.entity_id,
        # If passed in, we update value. Passing None will remove old value.
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


@callback
def _entry_dict(entry: er.RegistryEntry) -> dict[str, Any]:
    """Convert entry to API format."""
    return {
        "area_id": entry.area_id,
        "config_entry_id": entry.config_entry_id,
        "device_id": entry.device_id,
        "disabled_by": entry.disabled_by,
        "has_entity_name": entry.has_entity_name,
        "entity_category": entry.entity_category,
        "entity_id": entry.entity_id,
        "hidden_by": entry.hidden_by,
        "icon": entry.icon,
        "id": entry.id,
        "unique_id": entry.unique_id,
        "name": entry.name,
        "original_name": entry.original_name,
        "platform": entry.platform,
    }


@callback
def _entry_ext_dict(entry: er.RegistryEntry) -> dict[str, Any]:
    """Convert entry to API format."""
    data = _entry_dict(entry)
    data["capabilities"] = entry.capabilities
    data["device_class"] = entry.device_class
    data["options"] = entry.options
    data["original_device_class"] = entry.original_device_class
    data["original_icon"] = entry.original_icon
    return data
