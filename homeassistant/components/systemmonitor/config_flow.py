"""Adds config flow for System Monitor."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaCommonFlowHandler,
    SchemaConfigFlowHandler,
    SchemaFlowFormStep,
    SchemaFlowMenuStep,
)
from homeassistant.helpers.selector import TextSelector
from homeassistant.util import slugify

from .const import CONF_INDEX, CONF_PROCESS, DOMAIN


async def get_remove_sensor_schema(handler: SchemaCommonFlowHandler) -> vol.Schema:
    """Return schema for sensor removal."""
    return vol.Schema(
        {
            vol.Required(CONF_INDEX): cv.multi_select(
                {
                    str(index): config[CONF_PROCESS]
                    for index, config in enumerate(handler.options[SENSOR_DOMAIN])
                },
            )
        }
    )


async def validate_sensor_setup(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Validate sensor input."""
    # Standard behavior is to merge the result with the options.
    # In this case, we want to add a sub-item so we update the options directly.
    sensors: list[dict[str, Any]] = handler.options.setdefault(SENSOR_DOMAIN, [])
    sensors.append(user_input)
    return {}


async def validate_remove_sensor(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Validate remove sensor."""
    removed_indexes: set[str] = set(user_input[CONF_INDEX])

    # Standard behavior is to merge the result with the options.
    # In this case, we want to remove sub-items so we update the options directly.
    entity_registry = er.async_get(handler.parent_handler.hass)
    sensors: list[dict[str, Any]] = []
    sensor: dict[str, Any]
    for index, sensor in enumerate(handler.options[SENSOR_DOMAIN]):
        if str(index) not in removed_indexes:
            sensors.append(sensor)
        elif entity_id := entity_registry.async_get_entity_id(
            SENSOR_DOMAIN, DOMAIN, slugify(f"process_{sensor[CONF_PROCESS]}")
        ):
            entity_registry.async_remove(entity_id)
    handler.options[SENSOR_DOMAIN] = sensors
    return {}


SENSOR_SETUP = vol.Schema(
    {
        vol.Required(CONF_PROCESS): TextSelector(),
    }
)

CONFIG_FLOW = {
    "user": SchemaFlowFormStep(schema=vol.Schema({})),
}
OPTIONS_FLOW = {
    "init": SchemaFlowMenuStep(["add_process", "remove_process"]),
    "add_process": SchemaFlowFormStep(
        SENSOR_SETUP,
        suggested_values=None,
        validate_user_input=validate_sensor_setup,
    ),
    "remove_process": SchemaFlowFormStep(
        get_remove_sensor_schema,
        suggested_values=None,
        validate_user_input=validate_remove_sensor,
    ),
}


class ScrapeConfigFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle a config flow for System Monitor."""

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW

    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""
        return "System Monitor"
