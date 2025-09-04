"""Provides device automations for Device tracker."""

from __future__ import annotations

from operator import attrgetter

import voluptuous as vol

from homeassistant.components.zone import (
    DOMAIN as DOMAIN_ZONE,
    condition as zone_condition,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_CONDITION,
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_ENTITY_ID,
    CONF_TYPE,
    CONF_ZONE,
    STATE_HOME,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import (
    condition,
    config_validation as cv,
    entity_registry as er,
)
from homeassistant.helpers.config_validation import DEVICE_CONDITION_BASE_SCHEMA
from homeassistant.helpers.typing import ConfigType, TemplateVarsType

from .const import DOMAIN

LEGACY_CONDITION_TYPES = {"is_home", "is_not_home"}
ZONE_CONDITION_TYPES = {"is_in_zone", "is_not_in_zone"}

CONDITION_TYPES = (*LEGACY_CONDITION_TYPES, *ZONE_CONDITION_TYPES)

CONDITION_SCHEMA = DEVICE_CONDITION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_ENTITY_ID): cv.entity_id_or_uuid,
        vol.Required(CONF_TYPE): vol.In(CONDITION_TYPES),
        vol.Optional(CONF_ZONE): cv.entity_domain(DOMAIN_ZONE),
    }
)


async def async_get_conditions(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, str]]:
    """List device conditions for Device tracker devices."""
    registry = er.async_get(hass)
    conditions = []

    # Get all the integrations entities for this device
    for entry in er.async_entries_for_device(registry, device_id):
        if entry.domain != DOMAIN:
            continue

        # Add conditions for each entity that belongs to this integration
        base_condition = {
            CONF_CONDITION: "device",
            CONF_DEVICE_ID: device_id,
            CONF_DOMAIN: DOMAIN,
            CONF_ENTITY_ID: entry.id,
        }

        conditions += [{**base_condition, CONF_TYPE: cond} for cond in CONDITION_TYPES]

    return conditions


def async_get_condition_capabilities(
    hass: HomeAssistant, config: ConfigType
) -> dict[str, vol.Schema]:
    """List condition capabilities."""
    if config[CONF_TYPE] in LEGACY_CONDITION_TYPES:
        return {}

    zones = {
        ent.entity_id: ent.name
        for ent in sorted(hass.states.async_all(DOMAIN_ZONE), key=attrgetter("name"))
    }
    return {
        "extra_fields": vol.Schema(
            {
                vol.Required(CONF_ZONE): vol.In(zones),
            }
        )
    }


@callback
def async_condition_from_config(
    hass: HomeAssistant, config: ConfigType
) -> condition.ConditionCheckerType:
    """Create a function to test a device condition."""
    registry = er.async_get(hass)
    entity_id = er.async_resolve_entity_id(registry, config[ATTR_ENTITY_ID])
    reverse = config[CONF_TYPE] == "is_not_home"

    @callback
    def test_is_state(hass: HomeAssistant, variables: TemplateVarsType) -> bool:
        """Test if an entity is a certain state."""
        if config[CONF_TYPE] in ZONE_CONDITION_TYPES:
            return _is_in_zone(hass, config, entity_id)

        result = condition.state(hass, entity_id, STATE_HOME)
        if reverse:
            result = not result
        return result

    return test_is_state


def _is_in_zone(hass: HomeAssistant, config: ConfigType, entity_id: str | None) -> bool:
    """Test if an entity is in a zone."""
    result = zone_condition.zone(hass, config[CONF_ZONE], entity_id)
    if config[CONF_TYPE] == "is_in_zone":
        return result
    return not result
