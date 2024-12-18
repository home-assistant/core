"""Config flow for the Bayesian integration."""

from collections.abc import Mapping
from enum import StrEnum
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.alarm_control_panel import DOMAIN as ALARM_DOMAIN
from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.calendar import DOMAIN as CALENDAR_DOMAIN
from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.components.cover import DOMAIN as COVER_DOMAIN
from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER_DOMAIN
from homeassistant.components.input_boolean import DOMAIN as INPUT_BOLEAN_DOMAIN
from homeassistant.components.input_number import DOMAIN as INPUT_NUMBER_DOMAIN
from homeassistant.components.input_text import DOMAIN as INPUT_TEXT_DOMAIN
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.components.notify import DOMAIN as NOTIFY_DOMAIN
from homeassistant.components.number import DOMAIN as NUMBER_DOMAIN
from homeassistant.components.person import DOMAIN as PERSON_DOMAIN
from homeassistant.components.select import DOMAIN as SELECT_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.sun import DOMAIN as SUN_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.components.todo import DOMAIN as TODO_DOMAIN
from homeassistant.components.update import DOMAIN as UPDATE_DOMAIN
from homeassistant.components.weather import DOMAIN as WEATHER_DOMAIN
from homeassistant.components.zone import DOMAIN as ZONE_DOMAIN
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
)

from .binary_sensor import above_greater_than_below, no_overlapping
from .const import (
    CONF_INDEX,
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
USER = "user"
OBSERVATION_SELECTOR = "observation_selector"
ALLOWED_STATE_DOMAINS = [
    ALARM_DOMAIN,
    CALENDAR_DOMAIN,
    CLIMATE_DOMAIN,
    COVER_DOMAIN,
    DEVICE_TRACKER_DOMAIN,
    INPUT_BOLEAN_DOMAIN,
    INPUT_NUMBER_DOMAIN,
    INPUT_TEXT_DOMAIN,
    LIGHT_DOMAIN,
    MEDIA_PLAYER_DOMAIN,
    NOTIFY_DOMAIN,
    NUMBER_DOMAIN,
    PERSON_DOMAIN,
    "schedule",  # Avoids an import that would introduce a dependency.
    SELECT_DOMAIN,
    SENSOR_DOMAIN,
    SUN_DOMAIN,
    SWITCH_DOMAIN,
    TODO_DOMAIN,
    UPDATE_DOMAIN,
    WEATHER_DOMAIN,
]
ALLOWED_NUMERIC_DOMAINS = [
    SENSOR_DOMAIN,
    INPUT_NUMBER_DOMAIN,
    NUMBER_DOMAIN,
    TODO_DOMAIN,
    ZONE_DOMAIN,
]


class ObservationTypes(StrEnum):
    """StrEnum for all the different observation types."""

    STATE = CONF_STATE
    NUMERIC_STATE = "numeric_state"
    TEMPLATE = CONF_TEMPLATE


class OptionsFlowSteps(StrEnum):
    """StrEnum for all the different options flow steps."""

    INIT = "init"
    BASE_OPTIONS = "base_options"
    ADD_OBSERVATION = OBSERVATION_SELECTOR
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


OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Required(
            CONF_PROBABILITY_THRESHOLD, default=DEFAULT_PROBABILITY_THRESHOLD * 100
        ): vol.All(
            selector.NumberSelector(
                selector.NumberSelectorConfig(
                    mode=selector.NumberSelectorMode.SLIDER,
                    step=1.0,
                    min=0,
                    max=100,
                    unit_of_measurement="%",
                ),
            ),
            vol.Range(
                min=0,
                max=100,
                min_included=False,
                max_included=False,
                msg="extreme_threshold_error",
            ),
        ),
        vol.Required(CONF_PRIOR, default=DEFAULT_PROBABILITY_THRESHOLD * 100): vol.All(
            selector.NumberSelector(
                selector.NumberSelectorConfig(
                    mode=selector.NumberSelectorMode.SLIDER,
                    step=1.0,
                    min=0,
                    max=100,
                    unit_of_measurement="%",
                ),
            ),
            vol.Range(
                min=0,
                max=100,
                min_included=False,
                max_included=False,
                msg="extreme_prior_error",
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

OBSERVATION_BOILERPLATE = vol.Schema(
    {
        vol.Required(CONF_P_GIVEN_T): vol.All(
            selector.NumberSelector(
                selector.NumberSelectorConfig(
                    mode=selector.NumberSelectorMode.SLIDER,
                    step=1.0,
                    min=0,
                    max=100,
                    unit_of_measurement="%",
                ),
            ),
            vol.Range(
                min=0,
                max=100,
                min_included=False,
                max_included=False,
                msg="extreme_prob_given_error",
            ),
        ),
        vol.Required(CONF_P_GIVEN_F): vol.All(
            selector.NumberSelector(
                selector.NumberSelectorConfig(
                    mode=selector.NumberSelectorMode.SLIDER,
                    step=1.0,
                    min=0,
                    max=100,
                    unit_of_measurement="%",
                ),
            ),
            vol.Range(
                min=0,
                max=100,
                min_included=False,
                max_included=False,
                msg="extreme_prob_given_error",
            ),
        ),
        vol.Required(CONF_NAME): selector.TextSelector(),
    }
)

ADD_ANOTHER_BOX_SCHEMA = vol.Schema({vol.Optional("add_another"): cv.boolean})

STATE_SUBSCHEMA = vol.Schema(
    {
        vol.Required(CONF_ENTITY_ID): selector.EntitySelector(
            selector.EntitySelectorConfig(domain=ALLOWED_STATE_DOMAINS)
        ),
        vol.Required(CONF_TO_STATE): selector.TextSelector(
            selector.TextSelectorConfig(
                multiline=False, type=selector.TextSelectorType.TEXT, multiple=False
            )  # ideally this would be a state selector context-linked to the above entity.
        ),
    },
).extend(OBSERVATION_BOILERPLATE.schema)

NUMERIC_STATE_SUBSCHEMA = vol.Schema(
    {
        vol.Required(CONF_ENTITY_ID): selector.EntitySelector(
            selector.EntitySelectorConfig(domain=ALLOWED_NUMERIC_DOMAINS)
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
).extend(OBSERVATION_BOILERPLATE.schema)


TEMPLATE_SUBSCHEMA = vol.Schema(
    {
        vol.Required(CONF_VALUE_TEMPLATE): selector.TemplateSelector(
            selector.TemplateSelectorConfig(),
        ),
    },
).extend(OBSERVATION_BOILERPLATE.schema)


def _convert_percentages_to_fractions(
    data: dict[str, str | float | int],
) -> dict[str, str | float]:
    """Convert percentage probability values in a dictionary to fractions."""
    probabilities = [
        CONF_P_GIVEN_T,
        CONF_P_GIVEN_F,
        CONF_PRIOR,
        CONF_PROBABILITY_THRESHOLD,
    ]
    return {
        key: (
            value / 100
            if isinstance(value, (int, float)) and key in probabilities
            else value
        )
        for key, value in data.items()
    }


def _convert_fractions_to_percentages(
    data: dict[str, str | float],
) -> dict[str, str | float]:
    """Convert fraction probability values in a dictionary to percentages."""
    probabilities = [
        CONF_P_GIVEN_T,
        CONF_P_GIVEN_F,
        CONF_PRIOR,
        CONF_PROBABILITY_THRESHOLD,
    ]
    return {
        key: (
            value * 100
            if isinstance(value, (int, float)) and key in probabilities
            else value
        )
        for key, value in data.items()
    }


async def _get_select_observation_schema(
    handler: SchemaCommonFlowHandler,
) -> vol.Schema:
    """Return menu schema for selecting an observation for editing."""
    return vol.Schema(
        {
            vol.Required(CONF_INDEX): vol.In(
                {
                    str(index): f"{config.get(CONF_NAME)} ({config[CONF_PLATFORM]})"
                    for index, config in enumerate(handler.options[CONF_OBSERVATIONS])
                },
            )
        }
    )


async def _get_remove_observation_schema(
    handler: SchemaCommonFlowHandler,
) -> vol.Schema:
    """Return menu schema for multi-selecting observations for removal."""
    return vol.Schema(
        {
            vol.Required(CONF_INDEX): cv.multi_select(
                {
                    str(index): f"{config.get(CONF_NAME)} ({config[CONF_PLATFORM]})"
                    for index, config in enumerate(handler.options[CONF_OBSERVATIONS])
                },
            )
        }
    )


async def _get_flow_step_for_editing(
    user_input: dict[str, Any],
) -> str:
    """Choose which observation config flow form step to show depending on observation type selected."""

    observations: list[dict[str, Any]] = user_input[CONF_OBSERVATIONS]
    selected_idx = int(user_input[CONF_INDEX])

    return str(observations[selected_idx][CONF_PLATFORM])


async def _get_state_schema(
    handler: SchemaCommonFlowHandler,
) -> vol.Schema:
    """Return the state schema, without an add_another box if editing."""

    if not hasattr(handler, "options") or handler.options.get(CONF_INDEX) is None:
        return STATE_SUBSCHEMA.extend(ADD_ANOTHER_BOX_SCHEMA.schema)

    return STATE_SUBSCHEMA


async def _get_numeric_state_schema(
    handler: SchemaCommonFlowHandler,
) -> vol.Schema:
    """Return the numeric_state schema, without an add_another box if editing."""

    if not hasattr(handler, "options") or handler.options.get(CONF_INDEX) is None:
        return NUMERIC_STATE_SUBSCHEMA.extend(ADD_ANOTHER_BOX_SCHEMA.schema)

    return NUMERIC_STATE_SUBSCHEMA


async def _get_template_schema(
    handler: SchemaCommonFlowHandler,
) -> vol.Schema:
    """Return the template schema, without an add_another box if editing."""

    if not hasattr(handler, "options") or handler.options.get(CONF_INDEX) is None:
        return TEMPLATE_SUBSCHEMA.extend(ADD_ANOTHER_BOX_SCHEMA.schema)

    return TEMPLATE_SUBSCHEMA


async def _add_more_or_end(
    user_input: dict[str, Any],
) -> str | None:
    """Choose whether to add another observation or end the flow."""
    if user_input.get("add_another", False):
        return OBSERVATION_SELECTOR
    return None


async def _get_base_suggested_values(
    handler: SchemaCommonFlowHandler,
) -> dict[str, Any]:
    """Return suggested values for the base sensor options."""

    return _convert_fractions_to_percentages(dict(handler.options))


async def _get_observation_values_if_editing(
    handler: SchemaCommonFlowHandler,
) -> dict[str, Any]:
    """Only if editing observations in options flow, get the values. Otherwise leave blank."""
    if idx := handler.options.get(CONF_INDEX):
        return _convert_fractions_to_percentages(
            dict(handler.options[CONF_OBSERVATIONS][int(idx)])
        )
    return {}


async def _validate_user(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Validate user input for the basic settings and convert to fractions for storage."""
    user_input = _convert_percentages_to_fractions(user_input)
    return {**user_input}


def _validate_probabilities_given(
    user_input: dict[str, Any],
) -> None:
    """Raise errors for invalid probability_given_true/false."""
    if user_input[CONF_P_GIVEN_T] == user_input[CONF_P_GIVEN_F]:
        raise SchemaFlowError("equal_probabilities")


async def _validate_observation_setup(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Validate an observation input and manually update options with observations as they are nested items."""
    _validate_probabilities_given(user_input)

    # add_another is really just a variable for controlling the flow
    add_another: bool = user_input.pop("add_another", False)

    user_input = _convert_percentages_to_fractions(user_input)

    # Standard behavior is to merge the result with the options.
    # In this case, we want to add a sub-item so we update the options directly.
    observations: list[dict[str, Any]] = handler.options.setdefault(
        CONF_OBSERVATIONS, []
    )

    if idx := handler.options.get(CONF_INDEX):
        # if there is an index, that means we are in observation editing mode and we want to overwrite not append
        user_input[CONF_PLATFORM] = observations[int(idx)][CONF_PLATFORM]
        if user_input[CONF_PLATFORM] == ObservationTypes.NUMERIC_STATE:
            above_greater_than_below(user_input)
            draft_observations = [*observations, user_input]
            draft_observations.remove(observations[int(idx)])
            no_overlapping(draft_observations)

        observations[int(idx)] = user_input

        # remove the index so it can not be saved
        handler.options.pop(CONF_INDEX, None)
    elif handler.parent_handler.cur_step is not None:
        # if we are in adding mode we need to record the platform from the step id
        user_input[CONF_PLATFORM] = handler.parent_handler.cur_step["step_id"]
        if user_input[CONF_PLATFORM] == ObservationTypes.NUMERIC_STATE:
            above_greater_than_below(user_input)
            no_overlapping([*observations, user_input])

        observations.append(user_input)

    _LOGGER.debug("Added observation with settings: %s", user_input)
    return {"add_another": True} if add_another else {}


async def _validate_remove_observation(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Delete observation(s)."""
    observations: list[dict[str, Any]] = handler.options[CONF_OBSERVATIONS]
    indexes: set[int] = {int(x) for x in user_input[CONF_INDEX]}

    # Standard behavior is to merge the result with the options.
    # In this case, we want to remove nested items so we update the options directly.
    # Remove the last indexes first so subsequent items to be removed aren't shifted
    for index in sorted(indexes, reverse=True):
        observations.pop(index)

    _LOGGER.debug("Deleted observations: '%s'", observations)
    return {}


CONFIG_FLOW: dict[str, SchemaFlowMenuStep | SchemaFlowFormStep] = {
    str(USER): SchemaFlowFormStep(
        CONFIG_SCHEMA,
        validate_user_input=_validate_user,
        next_step=OBSERVATION_SELECTOR,
    ),
    str(OBSERVATION_SELECTOR): SchemaFlowMenuStep(
        [typ.value for typ in ObservationTypes]
    ),
    str(ObservationTypes.STATE): SchemaFlowFormStep(
        _get_state_schema,
        next_step=_add_more_or_end,
        validate_user_input=_validate_observation_setup,
        suggested_values=_get_observation_values_if_editing,
    ),
    str(ObservationTypes.NUMERIC_STATE): SchemaFlowFormStep(
        _get_numeric_state_schema,
        next_step=_add_more_or_end,
        validate_user_input=_validate_observation_setup,
        suggested_values=_get_observation_values_if_editing,
    ),
    str(ObservationTypes.TEMPLATE): SchemaFlowFormStep(
        _get_template_schema,
        next_step=_add_more_or_end,
        validate_user_input=_validate_observation_setup,
        suggested_values=_get_observation_values_if_editing,
    ),
}

OPTIONS_FLOW: dict[str, SchemaFlowMenuStep | SchemaFlowFormStep] = {
    str(OptionsFlowSteps.INIT): SchemaFlowMenuStep(
        OptionsFlowSteps.list_primary_steps()
    ),
    str(OptionsFlowSteps.BASE_OPTIONS): SchemaFlowFormStep(
        OPTIONS_SCHEMA,
        suggested_values=_get_base_suggested_values,
        validate_user_input=_validate_user,
    ),
    str(OptionsFlowSteps.SELECT_EDIT_OBSERVATION): SchemaFlowFormStep(
        _get_select_observation_schema,
        suggested_values=None,
        next_step=_get_flow_step_for_editing,
    ),
    str(OptionsFlowSteps.REMOVE_OBSERVATION): SchemaFlowFormStep(
        _get_remove_observation_schema,
        suggested_values=None,
        validate_user_input=_validate_remove_observation,
    ),
}
OPTIONS_FLOW.update(CONFIG_FLOW)


class BayesianConfigFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Bayesian config flow."""

    VERSION = 1
    MINOR_VERSION = 1

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW

    def async_config_entry_title(self, options: Mapping[str, str]) -> str:
        """Return config entry title."""
        name: str = options[CONF_NAME]
        return name
