"""Websocket API for Group integration."""

from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID, CONF_ENTITIES
from homeassistant.core import HomeAssistant, callback, split_entity_id
from homeassistant.helpers import config_validation as cv, entity_registry as er

from .const import CONF_HIDE_MEMBERS, DOMAIN, GROUP_TYPES
from .util import async_hide_members


def async_setup(hass: HomeAssistant) -> None:
    """Set up the Group websocket API."""
    websocket_api.async_register_command(hass, websocket_groups_for_entity)
    websocket_api.async_register_command(hass, websocket_add_entity_to_group)


def _group_type_for_entity_id(entity_id: str) -> str | None:
    """Return the compatible group type for an entity."""
    domain = split_entity_id(entity_id)[0]
    if domain in GROUP_TYPES:
        return domain
    return None


def _group_entity_id_for_config_entry(
    registry: er.EntityRegistry, entry: ConfigEntry
) -> str | None:
    """Return the entity ID for a group config entry."""
    entries = er.async_entries_for_config_entry(registry, entry.entry_id)
    return entries[0].entity_id if entries else None


def _compatible_group_entries(
    hass: HomeAssistant, entity_id: str
) -> tuple[str | None, list[ConfigEntry]]:
    """Return compatible group config entries for an entity."""
    group_type = _group_type_for_entity_id(entity_id)
    if group_type is None:
        return None, []

    entries = [
        entry
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.options.get("group_type") == group_type
    ]
    return group_type, entries


@callback
@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "group/groups_for_entity",
        vol.Required(ATTR_ENTITY_ID): cv.entity_id,
    }
)
def websocket_groups_for_entity(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """List compatible groups for an entity."""
    entity_id = msg[ATTR_ENTITY_ID]
    group_type, entries = _compatible_group_entries(hass, entity_id)
    registry = er.async_get(hass)

    connection.send_result(
        msg["id"],
        {
            "group_type": group_type,
            "groups": [
                {
                    "entry_id": entry.entry_id,
                    "entity_id": _group_entity_id_for_config_entry(registry, entry),
                    "name": entry.title,
                }
                for entry in entries
                if entity_id not in entry.options[CONF_ENTITIES]
            ],
        },
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "group/add_entity",
        vol.Required("entry_id"): str,
        vol.Required(ATTR_ENTITY_ID): cv.entity_id,
    }
)
@websocket_api.async_response
async def websocket_add_entity_to_group(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Add an entity to a group config entry."""
    entity_id = msg[ATTR_ENTITY_ID]
    entry = hass.config_entries.async_get_entry(msg["entry_id"])

    if entry is None or entry.domain != DOMAIN:
        connection.send_error(msg["id"], websocket_api.ERR_NOT_FOUND, "Group not found")
        return

    group_type = _group_type_for_entity_id(entity_id)
    if group_type is None or entry.options.get("group_type") != group_type:
        connection.send_error(
            msg["id"], "invalid_entity", "Entity cannot be added to this group"
        )
        return

    entities = list(entry.options[CONF_ENTITIES])
    if entity_id not in entities:
        entities.append(entity_id)
        hass.config_entries.async_update_entry(
            entry, options={**entry.options, CONF_ENTITIES: entities}
        )
        if entry.options[CONF_HIDE_MEMBERS]:
            async_hide_members(hass, [entity_id], er.RegistryEntryHider.INTEGRATION)
        await hass.config_entries.async_reload(entry.entry_id)

    connection.send_result(msg["id"], {"entities": entities})
