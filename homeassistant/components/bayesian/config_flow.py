"""Config flow for the Bayesian integration."""

from collections.abc import Mapping
from enum import StrEnum
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.alarm_control_panel import DOMAIN as ALARM_DOMAIN
from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
)
from homeassistant.components.calendar import DOMAIN as CALENDAR_DOMAIN
from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.components.cover import DOMAIN as COVER_DOMAIN
from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER_DOMAIN
from homeassistant.components.input_boolean import DOMAIN as INPUT_BOLEAN_DOMAIN
from homeassistant.components.input_number import DOMAIN as INPUT_NUMBER_DOMAIN
from homeassistant.components.input_text import DOMAIN as INPUT_TEXT_DOMAIN
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN, ConfigEntry
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
from homeassistant.config_entries import (
    ConfigSubentry,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
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
from homeassistant.core import callback
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
    BINARY_SENSOR_DOMAIN,
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
    ADD_OBSERVATION = OBSERVATION_SELECTOR


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


async def _select_observation_schema(
    obs_type: ObservationTypes,
) -> vol.Schema:
    """Return menu schema for selecting an observation for editing."""
    if obs_type == str(ObservationTypes.STATE):
        return STATE_SUBSCHEMA
    if obs_type == str(ObservationTypes.NUMERIC_STATE):
        return NUMERIC_STATE_SUBSCHEMA

    return TEMPLATE_SUBSCHEMA


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


async def _get_base_suggested_values(
    handler: SchemaCommonFlowHandler,
) -> dict[str, Any]:
    """Return suggested values for the base sensor options."""

    return _convert_fractions_to_percentages(dict(handler.options))


async def _get_observation_values_for_editing(
    subentry: ConfigSubentry,
) -> dict[str, Any]:
    """Only if editing observations in options flow, get the values. Otherwise leave blank."""

    return _convert_fractions_to_percentages(dict(subentry.data))


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


async def _validate_observation_subentry(
    obs_type: ObservationTypes,
    user_input: dict[str, Any],
    other_subentries: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Validate an observation input and manually update options with observations as they are nested items."""

    _validate_probabilities_given(user_input)
    user_input = _convert_percentages_to_fractions(user_input)

    # We need to record the observation type so add it to the user input.
    user_input[CONF_PLATFORM] = str(obs_type)

    if (
        user_input[CONF_PLATFORM] == ObservationTypes.NUMERIC_STATE
        and other_subentries is not None
    ):
        _LOGGER.debug(
            "Comparing with other subentries: %s", [*other_subentries, user_input]
        )
        above_greater_than_below(user_input)
        no_overlapping([*other_subentries, user_input])

    _LOGGER.debug("Processed observation with settings: %s", user_input)
    return user_input


CONFIG_FLOW: dict[str, SchemaFlowMenuStep | SchemaFlowFormStep] = {
    str(USER): SchemaFlowFormStep(
        CONFIG_SCHEMA,
        validate_user_input=_validate_user,
    ),
}

OPTIONS_FLOW: dict[str, SchemaFlowMenuStep | SchemaFlowFormStep] = {
    str(OptionsFlowSteps.INIT): SchemaFlowFormStep(
        OPTIONS_SCHEMA,
        suggested_values=_get_base_suggested_values,
        validate_user_input=_validate_user,
    ),
}
OPTIONS_FLOW.update(CONFIG_FLOW)


class BayesianConfigFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Bayesian config flow."""

    VERSION = 1
    MINOR_VERSION = 1

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentries supported by this integration."""
        return {"observation": ObservationSubentryFlowHandler}

    def async_config_entry_title(self, options: Mapping[str, str]) -> str:
        """Return config entry title."""
        name: str = options[CONF_NAME]
        return name


class ObservationSubentryFlowHandler(ConfigSubentryFlow):
    """Handle subentry flow for adding and modifying a topic."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """User flow to add a new topic."""

        return self.async_show_menu(
            step_id="user",
            menu_options=[typ.value for typ in ObservationTypes],
        )

    async def async_step_state(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """User flow to add a state observation."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                user_input = await _validate_observation_subentry(
                    ObservationTypes.STATE, user_input
                )
                return self.async_create_entry(
                    title=user_input.get(CONF_NAME),
                    data=user_input,
                )
            except SchemaFlowError as err:
                _LOGGER.error("Error validating observation subentry: %s", err)
                errors["base"] = str(err)

        return self.async_show_form(
            step_id=str(ObservationTypes.STATE),
            data_schema=self.add_suggested_values_to_schema(
                data_schema=STATE_SUBSCHEMA, suggested_values=None
            ),
            last_step=True,
            errors=errors,
        )

    async def async_step_numeric_state(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """User flow to add a new numeric state observation, (a numeric range)."""

        errors: dict[str, str] = {}

        if user_input is not None:
            other_subentries = [
                dict(subentry.data)
                for subentry in self._get_entry().subentries.values()
            ]
            try:
                user_input = await _validate_observation_subentry(
                    ObservationTypes.NUMERIC_STATE,
                    user_input,
                    other_subentries=other_subentries,
                )
                return self.async_create_entry(
                    title=user_input.get(CONF_NAME),
                    data=user_input,
                )
            except SchemaFlowError as err:
                _LOGGER.error("Error validating observation subentry: %s", err)
                errors["base"] = str(err)

        return self.async_show_form(
            step_id=str(ObservationTypes.NUMERIC_STATE),
            data_schema=self.add_suggested_values_to_schema(
                data_schema=NUMERIC_STATE_SUBSCHEMA, suggested_values=None
            ),
            last_step=True,
            errors=errors,
        )

    async def async_step_template(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """User flow to add a new template observation."""

        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                user_input = await _validate_observation_subentry(
                    ObservationTypes.TEMPLATE, user_input
                )
                return self.async_create_entry(
                    title=user_input.get(CONF_NAME),
                    data=user_input,
                )
            except SchemaFlowError as err:
                _LOGGER.error("Error validating observation subentry: %s", err)
                errors["base"] = str(err)

        return self.async_show_form(
            step_id=str(ObservationTypes.TEMPLATE),
            data_schema=self.add_suggested_values_to_schema(
                data_schema=TEMPLATE_SUBSCHEMA, suggested_values=None
            ),
            last_step=True,
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Enable the reconfigure button for observations."""
        errors: dict[str, str] = {}

        sub_entry = self._get_reconfigure_subentry()
        if user_input is not None:
            try:
                user_input = await _validate_observation_subentry(
                    sub_entry.data[CONF_PLATFORM], user_input
                )
                return self.async_update_and_abort(
                    self._get_entry(),
                    sub_entry,
                    title=user_input.get(CONF_NAME, sub_entry.data[CONF_NAME]),
                    data_updates=user_input,
                )
            except SchemaFlowError as err:
                _LOGGER.error("Error validating observation subentry: %s", err)
                errors["base"] = str(err)

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                data_schema=await _select_observation_schema(
                    sub_entry.data[CONF_PLATFORM]
                ),
                suggested_values=await _get_observation_values_for_editing(sub_entry),
            ),
            errors=errors,
        )
