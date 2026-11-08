"""Config flow for Trend integration."""

from collections.abc import Mapping
from typing import Any, cast, override

import probatio

from homeassistant.components.counter import DOMAIN as COUNTER_DOMAIN
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
    CONF_MIN_SAMPLES,
    CONF_SAMPLE_DURATION,
    DEFAULT_MAX_SAMPLES,
    DEFAULT_MIN_GRADIENT,
    DEFAULT_MIN_SAMPLES,
    DEFAULT_SAMPLE_DURATION,
    DOMAIN,
)

ALLOWED_DOMAINS = [COUNTER_DOMAIN, SENSOR_DOMAIN]


async def get_base_options_schema(handler: SchemaCommonFlowHandler) -> probatio.Schema:
    """Get base options schema."""
    return probatio.Schema(
        {
            probatio.Optional(CONF_ENTITY_ID): selector.EntitySelector(
                selector.EntitySelectorConfig(multiple=False, read_only=True),
            ),
            probatio.Optional(CONF_ATTRIBUTE): selector.AttributeSelector(
                selector.AttributeSelectorConfig(
                    entity_id=handler.options[CONF_ENTITY_ID]
                )
            ),
            probatio.Optional(CONF_INVERT, default=False): selector.BooleanSelector(),
        }
    )


async def get_extended_options_schema(
    handler: SchemaCommonFlowHandler,
) -> probatio.Schema:
    """Get extended options schema."""
    return (await get_base_options_schema(handler)).extend(
        {
            probatio.Optional(
                CONF_MAX_SAMPLES, default=DEFAULT_MAX_SAMPLES
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=2,
                    mode=selector.NumberSelectorMode.BOX,
                ),
            ),
            probatio.Optional(
                CONF_MIN_SAMPLES, default=DEFAULT_MIN_SAMPLES
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=2,
                    mode=selector.NumberSelectorMode.BOX,
                ),
            ),
            probatio.Optional(
                CONF_MIN_GRADIENT, default=DEFAULT_MIN_GRADIENT
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    step="any",
                    mode=selector.NumberSelectorMode.BOX,
                ),
            ),
            probatio.Optional(
                CONF_SAMPLE_DURATION, default=DEFAULT_SAMPLE_DURATION
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0,
                    mode=selector.NumberSelectorMode.BOX,
                    unit_of_measurement=UnitOfTime.SECONDS,
                ),
            ),
        }
    )


CONFIG_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_NAME): selector.TextSelector(),
        probatio.Required(CONF_ENTITY_ID): selector.EntitySelector(
            selector.EntitySelectorConfig(domain=ALLOWED_DOMAINS, multiple=False),
        ),
    }
)


class ConfigFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle a config or options flow for Trend."""

    MINOR_VERSION = 2

    config_flow = {
        "user": SchemaFlowFormStep(schema=CONFIG_SCHEMA, next_step="settings"),
        "settings": SchemaFlowFormStep(get_base_options_schema),
    }
    options_flow = {
        "init": SchemaFlowFormStep(get_extended_options_schema),
    }
    options_flow_reloads = True

    @override
    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""
        return cast(str, options[CONF_NAME])
