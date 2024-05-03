"""Config flow for Integration - Riemann sum integral integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

import voluptuous as vol

from homeassistant.components.counter import DOMAIN as COUNTER_DOMAIN
from homeassistant.components.input_number import DOMAIN as INPUT_NUMBER_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import CONF_METHOD, CONF_NAME, UnitOfTime
from homeassistant.helpers import selector
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaCommonFlowHandler,
    SchemaConfigFlowHandler,
    SchemaFlowFormStep,
    SchemaOptionsFlowHandler,
    entity_selector_without_own_entities,
)

from .const import (
    CONF_ROUND_DIGITS,
    CONF_SOURCE_SENSOR,
    CONF_UNIT_PREFIX,
    CONF_UNIT_TIME,
    DOMAIN,
    METHOD_LEFT,
    METHOD_RIGHT,
    METHOD_TRAPEZOIDAL,
)

UNIT_PREFIXES = [
    selector.SelectOptionDict(value="k", label="k (kilo)"),
    selector.SelectOptionDict(value="M", label="M (mega)"),
    selector.SelectOptionDict(value="G", label="G (giga)"),
    selector.SelectOptionDict(value="T", label="T (tera)"),
]
TIME_UNITS = [
    UnitOfTime.SECONDS,
    UnitOfTime.MINUTES,
    UnitOfTime.HOURS,
    UnitOfTime.DAYS,
]
INTEGRATION_METHODS = [
    METHOD_TRAPEZOIDAL,
    METHOD_LEFT,
    METHOD_RIGHT,
]


async def _get_options_dict(handler: SchemaCommonFlowHandler | None) -> dict:
    if handler is None or not isinstance(
        handler.parent_handler, SchemaOptionsFlowHandler
    ):
        entity_selector = selector.EntitySelector(
            selector.EntitySelectorConfig(
                domain=[COUNTER_DOMAIN, INPUT_NUMBER_DOMAIN, SENSOR_DOMAIN]
            )
        )
    else:
        entity_selector = entity_selector_without_own_entities(
            handler.parent_handler,
            selector.EntitySelectorConfig(
                domain=[COUNTER_DOMAIN, INPUT_NUMBER_DOMAIN, SENSOR_DOMAIN]
            ),
        )

    return {
        vol.Required(CONF_SOURCE_SENSOR): entity_selector,
        vol.Required(CONF_METHOD, default=METHOD_TRAPEZOIDAL): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=INTEGRATION_METHODS, translation_key=CONF_METHOD
            ),
        ),
        vol.Optional(CONF_ROUND_DIGITS): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0, max=6, mode=selector.NumberSelectorMode.BOX
            ),
        ),
        vol.Optional(CONF_UNIT_PREFIX): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=UNIT_PREFIXES, mode=selector.SelectSelectorMode.DROPDOWN
            )
        ),
        vol.Required(CONF_UNIT_TIME, default=UnitOfTime.HOURS): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=TIME_UNITS,
                mode=selector.SelectSelectorMode.DROPDOWN,
                translation_key=CONF_UNIT_TIME,
            ),
        ),
    }


async def _get_options_schema(handler: SchemaCommonFlowHandler) -> vol.Schema:
    return vol.Schema(await _get_options_dict(handler))


async def _get_config_schema(handler: SchemaCommonFlowHandler) -> vol.Schema:
    options = await _get_options_dict(handler)
    return vol.Schema({vol.Required(CONF_NAME): selector.TextSelector(), **options})


CONFIG_FLOW = {
    "user": SchemaFlowFormStep(_get_config_schema),
}

OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(_get_options_schema),
}


class ConfigFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle a config or options flow for Integration."""

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW

    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""
        return cast(str, options["name"])
