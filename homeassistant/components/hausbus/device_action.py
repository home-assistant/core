"""Defines device_actions of the haus-bus integration."""

import logging
from typing import Any

import voluptuous as vol
from voluptuous import Schema

from homeassistant.components.cover import DOMAIN as COVER_DOMAIN
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.typing import TemplateVarsType

from .const import DOMAIN

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

ACTION_COVER_TOGGLE = "toggle"


# ----------------------------
# read actions for a device
# ----------------------------
async def async_get_actions(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, str]]:
    """Returns the device actions for a device."""

    actions: list[dict[str, str]] = []

    registry = er.async_get(hass)
    entities = [ent for ent in registry.entities.values() if ent.device_id == device_id]
    _LOGGER.debug("entities for device_id %s are %s", device_id, entities)

    for ent in entities:
        if DOMAIN in ent.options:
            name = ent.name or ent.original_name
            hausbus_type = hass.data[DOMAIN]["device_types"].get(ent.entity_id)
            _LOGGER.debug("hausbus_type is %s", hausbus_type)

            _LOGGER.debug("name is %s type is %s", name, hausbus_type)

            # add cover.toggle as device action to make it appear in automation ui
            if hausbus_type == "HausbusCover":
                addAction(ACTION_COVER_TOGGLE, name, device_id, ent.entity_id, actions)

    _LOGGER.debug("async_get_actions id %s returns %s", device_id, actions)
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
# perform action
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

    if service == ACTION_COVER_TOGGLE:
        _LOGGER.debug("calling service cover.%s with %s", service, service_data)
        await hass.services.async_call(
            COVER_DOMAIN, service, service_data, context=context
        )
    else:
        _LOGGER.debug("calling service cover.%s with %s", service, service_data)
        await hass.services.async_call(DOMAIN, service, service_data, context=context)


# ----------------------------
# Action-Capabilities
# ----------------------------
async def async_get_action_capabilities(
    hass: HomeAssistant, config: dict[str, Any]
) -> dict[str, Schema]:
    """Returns capabilities for a device action."""

    service_type = config["type"]
    _LOGGER.debug("async_get_action_capabilities %s", service_type)

    result: dict[str, Schema] = {}

    entity_id = config["entity_id"]
    hausbus_type = hass.data[DOMAIN]["device_types"].get(entity_id)

    _LOGGER.debug("entity_id %s hausbus_type is %s", entity_id, hausbus_type)

    SCHEMA: Schema = vol.Schema({})  # default leeres Schema

    if hausbus_type == "HausbusCover":
        if service_type.startswith("toggle"):
            SCHEMA = vol.Schema({})  # hier kannst du gewünschte Felder definieren

    result = {"extra_fields": SCHEMA}
    _LOGGER.debug("returns %s", result)
    return result
