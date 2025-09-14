"""Defines device_actions of the haus-bus integration."""

import logging
from typing import Any

import voluptuous as vol
from voluptuous import Schema

from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.typing import TemplateVarsType

DOMAIN = "hausbus"

_LOGGER = logging.getLogger(__name__)

ACTION_SCHEMA = vol.Schema(
    {
        vol.Required("domain"): DOMAIN,
        vol.Required("type"): cv.string,
        vol.Required("device_id"): cv.string,
        vol.Required("entity_id"): cv.entity_id,
    },
    extra=vol.ALLOW_EXTRA,
)


# ----------------------------
# Actions für ein Device holen
# ----------------------------
async def async_get_actions(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, str]]:
    """Returns the device actions for a device."""

    actions: list[dict[str, str]] = []

    registry = er.async_get(hass)
    entities = [ent for ent in registry.entities.values() if ent.device_id == device_id]
    _LOGGER.debug("entities for %s returns %s", device_id, entities)
    for ent in entities:
        if DOMAIN in ent.options:
            hausbus_type = ent.options[DOMAIN].get("hausbus_type")
            hausbus_special_type = ent.options[DOMAIN].get("hausbus_special_type")
            name = ent.name or ent.original_name

            _LOGGER.debug(
                "%s is type %s special_type %s",
                name,
                hausbus_type,
                hausbus_special_type,
            )

            if hausbus_type == "HausbusCover":
                addAction("cover_toggle", name, device_id, ent.entity_id, actions)

    _LOGGER.debug("async_get_actions for %s returns %s", device_id, actions)
    return actions


def addAction(
    actionName: str,
    entityName: str | None,
    device_id: str,
    entity_id: str,
    actions: list[dict],
):
    """Adds an action to the given list."""
    actions.append(
        {
            "domain": DOMAIN,
            "type": f"{actionName} {entityName}",
            "device_id": device_id,
            "entity_id": entity_id,
        }
    )


# ----------------------------
# Action ausführen
# ----------------------------
async def async_call_action_from_config(
    hass: HomeAssistant,
    config: dict[str, Any],
    variables: TemplateVarsType,
    context: Context,
) -> None:
    """Processes an device action call."""
    service = config["type"].partition(" ")[0]
    service_data = {
        k: v for k, v in config.items() if k not in ("domain", "type", "device_id")
    }
    _LOGGER.debug("Rufe Service hausbus.%s mit %s", service, service_data)
    await hass.services.async_call(DOMAIN, service, service_data, context=context)


# ----------------------------
# Action-Capabilities
# ----------------------------
async def async_get_action_capabilities(
    hass: HomeAssistant, config: dict[str, Any]
) -> dict[str, Schema]:
    """Returns capabilities for a device action."""

    service_type = config["type"]
    _LOGGER.debug("async_get_action_capabilities %s ", service_type)

    result = {}

    registry = er.async_get(hass)
    entity = registry.entities.get(config["entity_id"])
    _LOGGER.debug("entity %s", entity)

    if entity and DOMAIN in entity.options:
        hausbus_type = entity.options[DOMAIN].get("hausbus_type")
        hausbus_special_type = entity.options[DOMAIN].get("hausbus_special_type")

        _LOGGER.debug(
            "hausbus_type %s hausbus_special_type %s",
            hausbus_type,
            hausbus_special_type,
        )

        if hausbus_type == "HausbusCover":
            if service_type.startswith("cover_toggle"):
                SCHEMA = vol.Schema({})

        result = {"extra_fields": SCHEMA}

    _LOGGER.debug("returns %s", result)
    return result
