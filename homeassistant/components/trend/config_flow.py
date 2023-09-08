"""Config flow for Trend integration."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

import voluptuous as vol

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import CONF_ATTRIBUTE, CONF_ENTITY_ID, CONF_NAME, UnitOfTime
from homeassistant.helpers import selector
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaCommonFlowHandler,
    SchemaConfigFlowHandler,
    SchemaFlowFormStep,
)

from .const import (
    CONF_INVERT,
    CONF_MAX_SAMPLES,
    CONF_MIN_GRADIENT,
    CONF_SAMPLE_DURATION,
    DOMAIN,
)


async def get_options_schema(handler: SchemaCommonFlowHandler) -> vol.Schema:
    """Get options schema."""
    return vol.Schema(
        {
            vol.Optional(CONF_ATTRIBUTE): selector.AttributeSelector(
                selector.AttributeSelectorConfig(
                    entity_id=handler.options[CONF_ENTITY_ID]
                )
            ),
            vol.Optional(CONF_INVERT, default=False): selector.BooleanSelector(),
            vol.Optional(CONF_MAX_SAMPLES, default=2): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0,
                    mode=selector.NumberSelectorMode.BOX,
                ),
            ),
            vol.Optional(CONF_MIN_GRADIENT, default=0.0): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0,
                    step=0.1,
                    mode=selector.NumberSelectorMode.BOX,
                ),
            ),
            vol.Optional(CONF_SAMPLE_DURATION, default=0): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0,
                    mode=selector.NumberSelectorMode.BOX,
                    unit_of_measurement=UnitOfTime.SECONDS,
                ),
            ),
        }
    )


CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): selector.TextSelector(),
        vol.Required(CONF_ENTITY_ID): selector.EntitySelector(
            selector.EntitySelectorConfig(domain=SENSOR_DOMAIN, multiple=False),
        ),
    }
)


class ConfigFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle a config or options flow for Trend."""

    config_flow = {
        "user": SchemaFlowFormStep(schema=CONFIG_SCHEMA, next_step="settings"),
        "settings": SchemaFlowFormStep(get_options_schema),
    }
    options_flow = {
        "init": SchemaFlowFormStep(get_options_schema),
    }

    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""
        return cast(str, options[CONF_NAME])
