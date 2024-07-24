"""Config flow for the Bayesian integration."""

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
)
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import (
    CONF_ABOVE,
    CONF_BELOW,
    CONF_DEVICE_CLASS,
    CONF_ENTITY_ID,
    CONF_NAME,
    CONF_VALUE_TEMPLATE,
)
from homeassistant.helpers import selector
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaCommonFlowHandler,
    SchemaConfigFlowHandler,
    SchemaFlowFormStep,
)

from .const import (
    CONF_P_GIVEN_F,
    CONF_P_GIVEN_T,
    CONF_PRIOR,
    CONF_PROBABILITY_THRESHOLD,
    DEFAULT_NAME,
    DEFAULT_PROBABILITY_THRESHOLD,
    DOMAIN,
)


async def _validate_mode(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Validate the threshold mode, and set limits to None if not set."""
    return {**user_input}


OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Required(
            CONF_PROBABILITY_THRESHOLD, default=DEFAULT_PROBABILITY_THRESHOLD * 100
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(
                mode=selector.NumberSelectorMode.SLIDER,
                step=1.0,
                min=0,
                max=100,
                unit_of_measurement="%",
            ),
        ),
        vol.Required(
            CONF_PRIOR, default=DEFAULT_PROBABILITY_THRESHOLD * 100
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(
                mode=selector.NumberSelectorMode.SLIDER,
                step=1.0,
                min=0,
                max=100,
                unit_of_measurement="%",
            ),
        ),
        vol.Optional(CONF_DEVICE_CLASS): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[cls.value for cls in BinarySensorDeviceClass],
                mode=selector.SelectSelectorMode.DROPDOWN,
                translation_key="binary_sensor_device_class",
                sort=True,
            ),
        ),
    }
)
SUBSCHEMA_BOILERPLATE = vol.Schema(
    {
        vol.Required(CONF_P_GIVEN_T): selector.NumberSelector(
            selector.NumberSelectorConfig(
                mode=selector.NumberSelectorMode.SLIDER,
                step=1.0,
                min=0,
                max=100,
                unit_of_measurement="%",
            ),
        ),
        vol.Required(CONF_P_GIVEN_F): selector.NumberSelector(
            selector.NumberSelectorConfig(
                mode=selector.NumberSelectorMode.SLIDER,
                step=1.0,
                min=0,
                max=100,
                unit_of_measurement="%",
            ),
        ),
    }
)

NUMERIC_STATE_SUBSCHEMA = vol.Schema(
    {
        vol.Required(CONF_ENTITY_ID): selector.EntitySelector(
            selector.EntitySelectorConfig(domain=SENSOR_DOMAIN)
        ),
        vol.Optional(CONF_ABOVE): selector.NumberSelector(
            selector.NumberSelectorConfig(
                mode=selector.NumberSelectorMode.BOX, step="any"
            ),
        ),
        vol.Optional(CONF_BELOW): selector.NumberSelector(
            selector.NumberSelectorConfig(
                mode=selector.NumberSelectorMode.BOX, step="any"
            ),
        ),
    },
).extend(SUBSCHEMA_BOILERPLATE.schema)

STATE_SUBSCHEMA = vol.Schema(
    {
        vol.Required(CONF_ENTITY_ID): selector.EntitySelector(
            selector.EntitySelectorConfig(domain=[SENSOR_DOMAIN, BINARY_SENSOR_DOMAIN])
        ),
        vol.Required(CONF_ENTITY_ID): selector.StateSelector(
            selector.StateSelectorConfig(
                entity_id="***THAT_ENTITY_ABOVE_DYNAMICALLY_SOMEHOW***"
            )
        ),
    },
).extend(SUBSCHEMA_BOILERPLATE.schema)

TEMPLATE_SUBSCHEMA = vol.Schema(
    {
        vol.Required(CONF_VALUE_TEMPLATE): selector.TemplateSelector(
            selector.TemplateSelectorConfig(),
        ),
    },
).extend(SUBSCHEMA_BOILERPLATE.schema)

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME, default=DEFAULT_NAME): selector.TextSelector(),
    }
).extend(OPTIONS_SCHEMA.schema)


CONFIG_FLOW = {
    "user": SchemaFlowFormStep(
        CONFIG_SCHEMA, preview="bayesian", validate_user_input=_validate_mode
    )
}

OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(
        OPTIONS_SCHEMA, preview="bayesian", validate_user_input=_validate_mode
    )
}


class BayesianConfigFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Example config flow."""

    # The schema version of the entries that it creates
    # Home Assistant will call your migrate method if the version changes
    VERSION = 1
    MINOR_VERSION = 1

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW

    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""
        name: str = options[CONF_NAME]
        return name
