"""Config flow for the Bayesian integration."""

from collections.abc import Mapping
from enum import StrEnum
from functools import partial
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
)
from homeassistant.components.input_number import DOMAIN as INPUT_NUMBER_DOMAIN
from homeassistant.components.number import DOMAIN as NUMBER_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import (
    CONF_ABOVE,
    CONF_BELOW,
    CONF_DEVICE_CLASS,
    CONF_ENTITY_ID,
    CONF_NAME,
    CONF_STATE,
    CONF_VALUE_TEMPLATE,
)
from homeassistant.helpers import selector
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaCommonFlowHandler,
    SchemaConfigFlowHandler,
    SchemaFlowFormStep,
    SchemaFlowMenuStep,
)

from .const import (
    CONF_P_GIVEN_F,
    CONF_P_GIVEN_T,
    CONF_PRIOR,
    CONF_PROBABILITY_THRESHOLD,
    DEFAULT_PROBABILITY_THRESHOLD,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class Observation_types(StrEnum):
    """StrEnum for all the different observation types."""

    STATE = "state"
    NUMERIC_STATE = "numeric_state"
    TEMPLATE = "template"

    @staticmethod
    def list() -> list[str]:
        """Return a list of the values."""

        return [c.value for c in Observation_types]


def generate_init_schema(obs_type: Observation_types, flow_type: str) -> vol.Schema:
    """Generate the initial schema depending on which observation type the user selects."""
    schema: dict[vol.Marker, Any] = {}

    if flow_type == "config":
        schema = {vol.Required(CONF_NAME): selector.TextSelector()}
    schema |= OPTIONS_SCHEMA.schema
    if obs_type == Observation_types.STATE:
        schema |= {
            vol.Required(CONF_ENTITY_ID): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain=[SENSOR_DOMAIN, BINARY_SENSOR_DOMAIN], multiple=True
                )
            ),
        }
    if obs_type == Observation_types.NUMERIC_STATE:
        schema |= {
            vol.Required(CONF_ENTITY_ID): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain=[SENSOR_DOMAIN, INPUT_NUMBER_DOMAIN, NUMBER_DOMAIN],
                    multiple=True,
                )
            ),
        }

    if obs_type == Observation_types.TEMPLATE:
        schema |= {
            vol.Required(CONF_VALUE_TEMPLATE + str(n)): selector.TemplateSelector(
                selector.TemplateSelectorConfig()
            )
            for n in range(10)
        }

    return vol.Schema(schema)


options_schema = partial(generate_init_schema, flow_type="options")

config_schema = partial(generate_init_schema, flow_type="config")


async def validate_user_input(
    obs_type: Observation_types,
    handler: SchemaCommonFlowHandler,
    user_input: dict[str, Any],
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


def _subschema_boilerplate(suffix: str) -> dict[vol.Marker, Any]:
    suffix = " " + suffix
    return {
        vol.Required(CONF_P_GIVEN_T + suffix): selector.NumberSelector(
            selector.NumberSelectorConfig(
                mode=selector.NumberSelectorMode.SLIDER,
                step=1.0,
                min=0,
                max=100,
                unit_of_measurement="%",
            ),
        ),
        vol.Required(CONF_P_GIVEN_F + suffix): selector.NumberSelector(
            selector.NumberSelectorConfig(
                mode=selector.NumberSelectorMode.SLIDER,
                step=1.0,
                min=0,
                max=100,
                unit_of_measurement="%",
            ),
        ),
    }


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
)

OPTIONS_FLOW = {"init": SchemaFlowFormStep(OPTIONS_SCHEMA)}


async def generate_state_schema(
    handler: SchemaCommonFlowHandler,
) -> vol.Schema:
    """Generate a schema for the further config variables for each chosen entity.

    Takes a handler.options like: {
        'name': 'cat',
        'probability_threshold': 37.0,
        'prior': 62.0,
        'entity_id': ['sensor.home_assistant_version', 'sensor.sun_next_dusk'],
        'device_class': 'occupancy'
    }
    And generates a config flow
    """
    user_input: dict[str, Any] = handler.options
    schema: dict[vol.Marker, Any] = {}

    for eid in user_input[CONF_ENTITY_ID]:
        _LOGGER.warning("Generating schema for eid: %s", eid)
        schema |= {
            vol.Required(eid + " " + CONF_STATE): selector.TextSelector(
                selector.TextSelectorConfig()
            ),
        }
        schema |= _subschema_boilerplate(eid)
    _LOGGER.warning("Generated schema: %s", schema)
    return vol.Schema(schema)


def generate_numeric_state_schema(user_input: dict[str, Any]) -> vol.Schema:
    """Generate a schema for the further config variables for each chosen entity."""

    schema: dict[vol.Marker, Any] = {}
    _LOGGER.warning(user_input)
    return vol.Schema(schema)


def generate_template_schema(user_input: dict[str, Any]) -> vol.Schema:
    """Generate a schema for the further config variables for each template."""

    schema: dict[vol.Marker, Any] = {}
    _LOGGER.warning(user_input)
    return vol.Schema(schema)


CONFIG_FLOW = {
    "user": SchemaFlowMenuStep(Observation_types.list()),
    Observation_types.STATE: SchemaFlowFormStep(
        config_schema(Observation_types.STATE),
        validate_user_input=partial(validate_user_input, Observation_types.STATE),
        next_step=Observation_types.STATE + "_config",
    ),
    Observation_types.STATE + "_config": SchemaFlowFormStep(
        generate_state_schema,
    ),
    Observation_types.NUMERIC_STATE: SchemaFlowFormStep(
        config_schema(Observation_types.NUMERIC_STATE),
        validate_user_input=partial(
            validate_user_input, Observation_types.NUMERIC_STATE
        ),
    ),
    Observation_types.TEMPLATE: SchemaFlowFormStep(
        config_schema(Observation_types.TEMPLATE),
        preview="template",
        validate_user_input=partial(validate_user_input, Observation_types.TEMPLATE),
    ),
}


class BayesianConfigFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Example config flow."""

    VERSION = 1
    MINOR_VERSION = 1

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW

    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""
        name: str = options[CONF_NAME]
        return name
