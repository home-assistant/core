"""Config flow for Derivative integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

import voluptuous as vol

from homeassistant.components.counter import DOMAIN as COUNTER_DOMAIN
from homeassistant.components.input_number import DOMAIN as INPUT_NUMBER_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_NAME,
    CONF_SOURCE,
    UnitOfTime,
)
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaCommonFlowHandler,
    SchemaConfigFlowHandler,
    SchemaFlowFormStep,
    SchemaOptionsFlowHandler,
)

from .const import (
    CONF_ROUND_DIGITS,
    CONF_TIME_WINDOW,
    CONF_UNIT_PREFIX,
    CONF_UNIT_TIME,
    DOMAIN,
)

UNIT_PREFIXES = [
    selector.SelectOptionDict(value="n", label="n (nano)"),
    selector.SelectOptionDict(value="µ", label="µ (micro)"),
    selector.SelectOptionDict(value="m", label="m (milli)"),
    selector.SelectOptionDict(value="k", label="k (kilo)"),
    selector.SelectOptionDict(value="M", label="M (mega)"),
    selector.SelectOptionDict(value="G", label="G (giga)"),
    selector.SelectOptionDict(value="T", label="T (tera)"),
    selector.SelectOptionDict(value="P", label="P (peta)"),
]
TIME_UNITS = [
    UnitOfTime.SECONDS,
    UnitOfTime.MINUTES,
    UnitOfTime.HOURS,
    UnitOfTime.DAYS,
]

ALLOWED_DOMAINS = [COUNTER_DOMAIN, INPUT_NUMBER_DOMAIN, SENSOR_DOMAIN]


@callback
def entity_selector_compatible(
    handler: SchemaOptionsFlowHandler,
) -> selector.EntitySelector:
    """Return an entity selector which compatible entities."""
    current = handler.hass.states.get(handler.options[CONF_SOURCE])
    unit_of_measurement = (
        current.attributes.get(ATTR_UNIT_OF_MEASUREMENT) if current else None
    )

    entities = [
        ent.entity_id
        for ent in handler.hass.states.async_all(ALLOWED_DOMAINS)
        if ent.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == unit_of_measurement
        and ent.domain in ALLOWED_DOMAINS
    ]

    return selector.EntitySelector(
        selector.EntitySelectorConfig(include_entities=entities)
    )


async def _get_options_dict(handler: SchemaCommonFlowHandler | None) -> dict:
    if handler is None or not isinstance(
        handler.parent_handler, SchemaOptionsFlowHandler
    ):
        entity_selector = selector.EntitySelector(
            selector.EntitySelectorConfig(domain=ALLOWED_DOMAINS)
        )
    else:
        entity_selector = entity_selector_compatible(handler.parent_handler)

    return {
        vol.Required(CONF_SOURCE): entity_selector,
        vol.Required(CONF_ROUND_DIGITS, default=2): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0,
                max=6,
                mode=selector.NumberSelectorMode.BOX,
                unit_of_measurement="decimals",
            ),
        ),
        vol.Required(CONF_TIME_WINDOW): selector.DurationSelector(),
        vol.Optional(CONF_UNIT_PREFIX): selector.SelectSelector(
            selector.SelectSelectorConfig(options=UNIT_PREFIXES),
        ),
        vol.Required(CONF_UNIT_TIME, default=UnitOfTime.HOURS): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=TIME_UNITS, translation_key="time_unit"
            ),
        ),
    }


async def _get_options_schema(handler: SchemaCommonFlowHandler) -> vol.Schema:
    return vol.Schema(await _get_options_dict(handler))


async def _get_config_schema(handler: SchemaCommonFlowHandler) -> vol.Schema:
    options = await _get_options_dict(handler)
    return vol.Schema(
        {
            vol.Required(CONF_NAME): selector.TextSelector(),
            **options,
        }
    )


CONFIG_FLOW = {
    "user": SchemaFlowFormStep(_get_config_schema),
}

OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(_get_options_schema),
}


class ConfigFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle a config or options flow for Derivative."""

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW

    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""
        return cast(str, options[CONF_NAME])
