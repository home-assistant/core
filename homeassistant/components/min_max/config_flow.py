"""Config flow for Min/Max integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

import voluptuous as vol

from homeassistant.components.input_number import DOMAIN as INPUT_NUMBER_DOMAIN
from homeassistant.components.number import DOMAIN as NUMBER_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import CONF_TYPE
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.helpers import selector
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaCommonFlowHandler,
    SchemaConfigFlowHandler,
    SchemaFlowFormStep,
)

from .const import CONF_ENTITY_IDS, CONF_ROUND_DIGITS, DOMAIN

_STATISTIC_MEASURES = [
    "min",
    "max",
    "mean",
    "median",
    "last",
    "range",
    "sum",
]


OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ENTITY_IDS): selector.EntitySelector(
            selector.EntitySelectorConfig(
                domain=[SENSOR_DOMAIN, NUMBER_DOMAIN, INPUT_NUMBER_DOMAIN],
                multiple=True,
            ),
        ),
        vol.Required(CONF_TYPE): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=_STATISTIC_MEASURES, translation_key=CONF_TYPE
            ),
        ),
        vol.Required(CONF_ROUND_DIGITS, default=2): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0, max=6, mode=selector.NumberSelectorMode.BOX
            ),
        ),
    }
)

CONFIG_SCHEMA = vol.Schema({})


async def migrate_to_groups(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Abort flow as migrate to groups."""
    raise AbortFlow("migrated_to_groups")


CONFIG_FLOW = {
    "user": SchemaFlowFormStep(CONFIG_SCHEMA, validate_user_input=migrate_to_groups),
}

OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(OPTIONS_SCHEMA),
}


class ConfigFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle a config or options flow for Min/Max."""

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW
    options_flow_reloads = True

    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""
        return cast(str, options["name"]) if "name" in options else ""
