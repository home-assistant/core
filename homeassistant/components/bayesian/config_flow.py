"""Config flow for the Bayesian integration."""

from collections.abc import Mapping
from enum import StrEnum
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
)
from homeassistant.components.input_boolean import DOMAIN as INPUT_BOLEAN_DOMAIN
from homeassistant.components.input_number import DOMAIN as INPUT_NUMBER_DOMAIN
from homeassistant.components.number import DOMAIN as NUMBER_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import (
    CONF_ABOVE,
    CONF_BELOW,
    CONF_DEVICE_CLASS,
    CONF_ENTITY_ID,
    CONF_NAME,
    CONF_PLATFORM,
    CONF_STATE,
    CONF_VALUE_TEMPLATE,
)
from homeassistant.helpers import selector
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaCommonFlowHandler,
    SchemaConfigFlowHandler,
    SchemaFlowError,
    SchemaFlowFormStep,
    SchemaFlowMenuStep,
    SchemaFlowStep,
)

from .const import (
    CONF_OBSERVATIONS,
    CONF_P_GIVEN_F,
    CONF_P_GIVEN_T,
    CONF_PRIOR,
    CONF_PROBABILITY_THRESHOLD,
    CONF_TEMPLATE,
    CONF_TO_STATE,
    DEFAULT_NAME,
    DEFAULT_PROBABILITY_THRESHOLD,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class ObservationTypes(StrEnum):
    """StrEnum for all the different observation types."""

    STATE = CONF_STATE
    NUMERIC_STATE = "numeric_state"
    TEMPLATE = CONF_TEMPLATE

    @staticmethod
    def list() -> list[str]:
        """Return a list of the values."""

        return [c.value for c in ObservationTypes]


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

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME, default=DEFAULT_NAME): selector.TextSelector(),
    }
).extend(OPTIONS_SCHEMA.schema)

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
        vol.Optional("add_another"): cv.boolean,
    }
)

STATE_SUBSCHEMA = vol.Schema(
    {
        vol.Required(CONF_PLATFORM): CONF_STATE,
        vol.Required(CONF_ENTITY_ID): selector.EntitySelector(
            selector.EntitySelectorConfig(
                domain=[SENSOR_DOMAIN, BINARY_SENSOR_DOMAIN, INPUT_BOLEAN_DOMAIN]
            )
        ),
        vol.Required(CONF_TO_STATE): selector.TextSelector(
            selector.TextSelectorConfig(
                multiline=False, type=selector.TextSelectorType.TEXT, multiple=False
            )  # ideally this would be a state selector context-linked to the above entity.
        ),
    },
).extend(SUBSCHEMA_BOILERPLATE.schema)

NUMERIC_STATE_SUBSCHEMA = vol.Schema(
    {
        CONF_PLATFORM: str(ObservationTypes.NUMERIC_STATE),
        vol.Required(CONF_ENTITY_ID): selector.EntitySelector(
            selector.EntitySelectorConfig(
                domain=[SENSOR_DOMAIN, INPUT_NUMBER_DOMAIN, NUMBER_DOMAIN]
            )
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

TEMPLATE_SUBSCHEMA = vol.Schema(
    {
        CONF_PLATFORM: CONF_TEMPLATE,
        vol.Required(CONF_VALUE_TEMPLATE): selector.TemplateSelector(
            selector.TemplateSelectorConfig(),
        ),
    },
).extend(SUBSCHEMA_BOILERPLATE.schema)


class ConfigFlowSteps(StrEnum):
    """StrEnum for all the different config steps."""

    USER = "user"
    OBSERVATION_SELECTOR = "observation_selector"


class OptionsFlowSteps(StrEnum):
    """StrEnum for all the different options flow steps."""

    INIT = "init"
    BASE_OPTIONS = "base_options"
    ADD_OBSERVATION = str(ConfigFlowSteps.OBSERVATION_SELECTOR)
    SELECT_EDIT_OBSERVATION = "select_edit_observation"
    EDIT_OBSERVATION = "edit_observation"
    REMOVE_OBSERVATION = "remove_observation"

    @staticmethod
    def list_primary_steps() -> list[str]:
        """Return a list of the values."""
        li = [c.value for c in OptionsFlowSteps]
        li.remove("init")
        li.remove("edit_observation")
        return li


async def _validate_user(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Validate the threshold mode, and set limits to None if not set."""
    if user_input[CONF_PRIOR] == 0:
        raise SchemaFlowError("prior_low_error")
    if user_input[CONF_PRIOR] == 100:
        raise SchemaFlowError("prior_high_error")
    if user_input[CONF_PROBABILITY_THRESHOLD] == 0:
        raise SchemaFlowError("threshold_low_error")
    if user_input[CONF_PROBABILITY_THRESHOLD] == 100:
        raise SchemaFlowError("threshold_high_error")
    user_input = _convert_percentages_to_fractions(user_input)
    return {**user_input}


async def validate_observation_setup(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Validate observation input."""

    if user_input[CONF_P_GIVEN_T] == user_input[CONF_P_GIVEN_F]:
        raise SchemaFlowError("equal_probabilities")

    if user_input[CONF_PLATFORM] == ObservationTypes.STATE:
        pass
    if user_input[CONF_PLATFORM] == ObservationTypes.NUMERIC_STATE:
        pass
    if user_input[CONF_PLATFORM] == ObservationTypes.TEMPLATE:
        pass
    # add_another is really just a variable for controlling the flow
    add_another: bool = user_input.pop("add_another", False)

    user_input = _convert_percentages_to_fractions(user_input)
    # Standard behavior is to merge the result with the options.
    # In this case, we want to add a sub-item so we update the options directly.
    observations: list[dict[str, Any]] = handler.options.setdefault(
        CONF_OBSERVATIONS, []
    )
    observations.append(user_input)
    return {"add_another": True} if add_another else {}


async def _choose_observation_step(
    user_input: dict[str, Any],
) -> ConfigFlowSteps | None:
    """Return next step_id for options flow according to template_type."""
    if user_input.get("add_another", False):
        return ConfigFlowSteps.OBSERVATION_SELECTOR
    return None


def _convert_percentages_to_fractions(
    data: dict[str, str | float | int],
) -> dict[str, str | float]:
    """Convert percentage values in a dictionary to fractions."""
    return {
        key: (value / 100 if isinstance(value, (int, float)) else value)
        for key, value in data.items()
    }


def _convert_fractions_to_percentages(
    data: dict[str, str | float],
) -> dict[str, str | float]:
    """Convert fraction values in a dictionary to percentages."""
    return {
        key: (value * 100 if isinstance(value, (float)) else value)
        for key, value in data.items()
    }


CONFIG_FLOW = {
    str(ConfigFlowSteps.USER): SchemaFlowFormStep(
        CONFIG_SCHEMA,
        validate_user_input=_validate_user,
        next_step=ConfigFlowSteps.OBSERVATION_SELECTOR,
    ),
    str(ConfigFlowSteps.OBSERVATION_SELECTOR): SchemaFlowMenuStep(
        ObservationTypes.list()
    ),
    str(ObservationTypes.STATE): SchemaFlowFormStep(
        STATE_SUBSCHEMA,
        next_step=_choose_observation_step,
        validate_user_input=validate_observation_setup,
        suggested_values=None,
    ),
    str(ObservationTypes.NUMERIC_STATE): SchemaFlowFormStep(
        NUMERIC_STATE_SUBSCHEMA,
        next_step=_choose_observation_step,
        validate_user_input=validate_observation_setup,
        suggested_values=None,
    ),
    str(ObservationTypes.TEMPLATE): SchemaFlowFormStep(
        TEMPLATE_SUBSCHEMA,
        next_step=_choose_observation_step,
        preview="bayesian",
        validate_user_input=validate_observation_setup,
        suggested_values=None,
    ),
}


async def _get_base_suggested_values(
    handler: SchemaCommonFlowHandler,
) -> dict[str, Any]:
    """Return suggested values for the sensor base options."""

    return _convert_fractions_to_percentages(dict(handler.options))


async def _get_edit_observation_suggested_values(
    handler: SchemaCommonFlowHandler,
) -> dict[str, Any]:  # TODO untested, borrowed from scrape
    """Return suggested values for observation editing."""
    idx: int = handler.flow_state["_idx"]
    return dict(handler.options[CONF_OBSERVATIONS][idx])


async def _get_select_observation_schema(
    handler: SchemaCommonFlowHandler,
) -> vol.Schema:  # TODO untested, borrowed from scrape
    """Return schema for selecting a observation."""
    return vol.Schema(
        {
            vol.Required("index"): vol.In(
                {
                    str(index): config[CONF_NAME]
                    for index, config in enumerate(handler.options[CONF_OBSERVATIONS])
                },
            )
        }
    )


async def _get_remove_observation_schema(
    handler: SchemaCommonFlowHandler,
) -> vol.Schema:  # TODO untested, borrowed from scrape
    """Return schema for observation removal."""
    return vol.Schema(
        {
            vol.Required("index"): cv.multi_select(
                {
                    str(index): config[CONF_NAME]
                    for index, config in enumerate(handler.options[CONF_OBSERVATIONS])
                },
            )
        }
    )


async def _get_edit_observation_schema(
    handler: SchemaCommonFlowHandler,
) -> vol.Schema:  # TODO
    """Select which schema to return depending on which observation type it is."""

    return  # TODO we will also need to drop the "add another" box from the schema here


OPTIONS_FLOW: dict[str, SchemaFlowStep] = {
    str(OptionsFlowSteps.INIT): SchemaFlowMenuStep(
        OptionsFlowSteps.list_primary_steps()
    ),
    str(OptionsFlowSteps.BASE_OPTIONS): SchemaFlowFormStep(
        OPTIONS_SCHEMA,
        validate_user_input=_validate_user,
        suggested_values=_get_base_suggested_values,
    ),
    str(OptionsFlowSteps.SELECT_EDIT_OBSERVATION): SchemaFlowFormStep(
        _get_select_observation_schema,
        suggested_values=None,
        next_step=str(OptionsFlowSteps.EDIT_OBSERVATION),
    ),
    str(OptionsFlowSteps.EDIT_OBSERVATION): SchemaFlowFormStep(
        _get_edit_observation_schema,
        suggested_values=_get_edit_observation_suggested_values,
    ),
    str(OptionsFlowSteps.REMOVE_OBSERVATION): SchemaFlowFormStep(
        _get_remove_observation_schema,
        suggested_values=None,
    ),
}
OPTIONS_FLOW.update(CONFIG_FLOW)


class BayesianConfigFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Example config flow."""

    # The schema version of the entries that it creates
    # Home Assistant will call your migrate method if the version changes
    VERSION = 1
    MINOR_VERSION = 1

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW

    def async_config_entry_title(self, options: Mapping[str, str]) -> str:
        """Return config entry title."""
        name: str = options[CONF_NAME]
        return name
