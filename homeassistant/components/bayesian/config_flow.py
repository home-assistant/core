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
from homeassistant.components.input_boolean import DOMAIN as INPUT_BOOLEAN_DOMAIN
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
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlowResult,
    ConfigSubentry,
    ConfigSubentryData,
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
from homeassistant.helpers import selector, translation
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaCommonFlowHandler,
    SchemaConfigFlowHandler,
    SchemaFlowError,
    SchemaFlowFormStep,
    SchemaFlowMenuStep,
)

from .binary_sensor import above_greater_than_below, no_overlapping
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
USER = "user"
OBSERVATION_SELECTOR = "observation_selector"
ALLOWED_STATE_DOMAINS = [
    ALARM_DOMAIN,
    BINARY_SENSOR_DOMAIN,
    CALENDAR_DOMAIN,
    CLIMATE_DOMAIN,
    COVER_DOMAIN,
    DEVICE_TRACKER_DOMAIN,
    INPUT_BOOLEAN_DOMAIN,
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
    """Convert percentage probability values in a dictionary to fractions for storing in the config entry."""
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
    """Convert fraction probability values in a dictionary to percentages for loading into the UI."""
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


def _select_observation_schema(
    obs_type: ObservationTypes,
) -> vol.Schema:
    """Return the schema for editing the correct observation (SubEntry) type."""
    if obs_type == str(ObservationTypes.STATE):
        return STATE_SUBSCHEMA
    if obs_type == str(ObservationTypes.NUMERIC_STATE):
        return NUMERIC_STATE_SUBSCHEMA

    return TEMPLATE_SUBSCHEMA


async def _get_base_suggested_values(
    handler: SchemaCommonFlowHandler,
) -> dict[str, Any]:
    """Return suggested values for the base sensor options."""

    return _convert_fractions_to_percentages(dict(handler.options))


def _get_observation_values_for_editing(
    subentry: ConfigSubentry,
) -> dict[str, Any]:
    """Return the values for editing in the observation subentry."""

    return _convert_fractions_to_percentages(dict(subentry.data))


async def _validate_user(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Modify user input to convert to fractions for storage. Validation is done entirely by the schemas."""
    user_input = _convert_percentages_to_fractions(user_input)
    return {**user_input}


def _validate_observation_subentry(
    obs_type: ObservationTypes,
    user_input: dict[str, Any],
    other_subentries: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Validate an observation input and manually update options with observations as they are nested items."""

    if user_input[CONF_P_GIVEN_T] == user_input[CONF_P_GIVEN_F]:
        raise SchemaFlowError("equal_probabilities")
    user_input = _convert_percentages_to_fractions(user_input)

    # Save the observation type in the user input as it is needed in binary_sensor.py
    user_input[CONF_PLATFORM] = str(obs_type)

    # Additional validation for multiple numeric state observations
    if (
        user_input[CONF_PLATFORM] == ObservationTypes.NUMERIC_STATE
        and other_subentries is not None
    ):
        _LOGGER.debug(
            "Comparing with other subentries: %s", [*other_subentries, user_input]
        )
        try:
            above_greater_than_below(user_input)
            no_overlapping([*other_subentries, user_input])
        except vol.Invalid as err:
            raise SchemaFlowError(err) from err

    _LOGGER.debug("Processed observation with settings: %s", user_input)
    return user_input


async def _validate_subentry_from_config_entry(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    # Standard behavior is to merge the result with the options.
    # In this case, we want to add a subentry so we update the options directly.
    observations: list[dict[str, Any]] = handler.options.setdefault(
        CONF_OBSERVATIONS, []
    )

    if handler.parent_handler.cur_step is not None:
        user_input[CONF_PLATFORM] = handler.parent_handler.cur_step["step_id"]
        user_input = _validate_observation_subentry(
            user_input[CONF_PLATFORM],
            user_input,
            other_subentries=handler.options[CONF_OBSERVATIONS],
        )
    observations.append(user_input)
    return {}


async def _get_description_placeholders(
    handler: SchemaCommonFlowHandler,
) -> dict[str, str]:
    # Current step is None when were are about to start the first step
    if handler.parent_handler.cur_step is None:
        return {"url": "https://www.home-assistant.io/integrations/bayesian/"}
    return {
        "parent_sensor_name": handler.options[CONF_NAME],
        "device_class_on": translation.async_translate_state(
            handler.parent_handler.hass,
            "on",
            BINARY_SENSOR_DOMAIN,
            platform=None,
            translation_key=None,
            device_class=handler.options.get(CONF_DEVICE_CLASS, None),
        ),
        "device_class_off": translation.async_translate_state(
            handler.parent_handler.hass,
            "off",
            BINARY_SENSOR_DOMAIN,
            platform=None,
            translation_key=None,
            device_class=handler.options.get(CONF_DEVICE_CLASS, None),
        ),
    }


async def _get_observation_menu_options(handler: SchemaCommonFlowHandler) -> list[str]:
    """Return the menu options for the observation selector."""
    options = [typ.value for typ in ObservationTypes]
    if handler.options.get(CONF_OBSERVATIONS):
        options.append("finish")
    return options


CONFIG_FLOW: dict[str, SchemaFlowMenuStep | SchemaFlowFormStep] = {
    str(USER): SchemaFlowFormStep(
        CONFIG_SCHEMA,
        validate_user_input=_validate_user,
        next_step=str(OBSERVATION_SELECTOR),
        description_placeholders=_get_description_placeholders,
    ),
    str(OBSERVATION_SELECTOR): SchemaFlowMenuStep(
        _get_observation_menu_options,
    ),
    str(ObservationTypes.STATE): SchemaFlowFormStep(
        STATE_SUBSCHEMA,
        next_step=str(OBSERVATION_SELECTOR),
        validate_user_input=_validate_subentry_from_config_entry,
        # Prevent the name of the bayesian sensor from being used as the suggested
        # name of the observations
        suggested_values=None,
        description_placeholders=_get_description_placeholders,
    ),
    str(ObservationTypes.NUMERIC_STATE): SchemaFlowFormStep(
        NUMERIC_STATE_SUBSCHEMA,
        next_step=str(OBSERVATION_SELECTOR),
        validate_user_input=_validate_subentry_from_config_entry,
        suggested_values=None,
        description_placeholders=_get_description_placeholders,
    ),
    str(ObservationTypes.TEMPLATE): SchemaFlowFormStep(
        TEMPLATE_SUBSCHEMA,
        next_step=str(OBSERVATION_SELECTOR),
        validate_user_input=_validate_subentry_from_config_entry,
        suggested_values=None,
        description_placeholders=_get_description_placeholders,
    ),
    "finish": SchemaFlowFormStep(),
}


OPTIONS_FLOW: dict[str, SchemaFlowMenuStep | SchemaFlowFormStep] = {
    str(OptionsFlowSteps.INIT): SchemaFlowFormStep(
        OPTIONS_SCHEMA,
        suggested_values=_get_base_suggested_values,
        validate_user_input=_validate_user,
        description_placeholders=_get_description_placeholders,
    ),
}


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

    @callback
    def async_create_entry(
        self,
        data: Mapping[str, Any],
        **kwargs: Any,
    ) -> ConfigFlowResult:
        """Finish config flow and create a config entry."""
        data = dict(data)
        observations = data.pop(CONF_OBSERVATIONS)
        subentries: list[ConfigSubentryData] = [
            ConfigSubentryData(
                data=observation,
                title=observation[CONF_NAME],
                subentry_type="observation",
                unique_id=None,
            )
            for observation in observations
        ]

        self.async_config_flow_finished(data)
        return super().async_create_entry(data=data, subentries=subentries, **kwargs)


class ObservationSubentryFlowHandler(ConfigSubentryFlow):
    """Handle subentry flow for adding and modifying a topic."""

    async def step_common(
        self,
        user_input: dict[str, Any] | None,
        obs_type: ObservationTypes,
        reconfiguring: bool = False,
    ) -> SubentryFlowResult:
        """Use common logic within the named steps."""

        errors: dict[str, str] = {}

        other_subentries = None
        if obs_type == str(ObservationTypes.NUMERIC_STATE):
            other_subentries = [
                dict(se.data) for se in self._get_entry().subentries.values()
            ]
        # If we are reconfiguring a subentry we don't want to compare with self
        if reconfiguring:
            sub_entry = self._get_reconfigure_subentry()
            if other_subentries is not None:
                other_subentries.remove(dict(sub_entry.data))

        if user_input is not None:
            try:
                user_input = _validate_observation_subentry(
                    obs_type,
                    user_input,
                    other_subentries=other_subentries,
                )
                if reconfiguring:
                    return self.async_update_and_abort(
                        self._get_entry(),
                        sub_entry,
                        title=user_input.get(CONF_NAME, sub_entry.data[CONF_NAME]),
                        data_updates=user_input,
                    )
                return self.async_create_entry(
                    title=user_input.get(CONF_NAME),
                    data=user_input,
                )
            except SchemaFlowError as err:
                errors["base"] = str(err)

        return self.async_show_form(
            step_id="reconfigure" if reconfiguring else str(obs_type),
            data_schema=self.add_suggested_values_to_schema(
                data_schema=_select_observation_schema(obs_type),
                suggested_values=_get_observation_values_for_editing(sub_entry)
                if reconfiguring
                else None,
            ),
            errors=errors,
            description_placeholders={
                "parent_sensor_name": self._get_entry().title,
                "device_class_on": translation.async_translate_state(
                    self.hass,
                    "on",
                    BINARY_SENSOR_DOMAIN,
                    platform=None,
                    translation_key=None,
                    device_class=self._get_entry().options.get(CONF_DEVICE_CLASS, None),
                ),
                "device_class_off": translation.async_translate_state(
                    self.hass,
                    "off",
                    BINARY_SENSOR_DOMAIN,
                    platform=None,
                    translation_key=None,
                    device_class=self._get_entry().options.get(CONF_DEVICE_CLASS, None),
                ),
            },
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """User flow to add a new observation."""

        return self.async_show_menu(
            step_id="user",
            menu_options=[typ.value for typ in ObservationTypes],
        )

    async def async_step_state(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """User flow to add a state observation. Function name must be in the format async_step_{observation_type}."""

        return await self.step_common(
            user_input=user_input, obs_type=ObservationTypes.STATE
        )

    async def async_step_numeric_state(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """User flow to add a new numeric state observation, (a numeric range). Function name must be in the format async_step_{observation_type}."""

        return await self.step_common(
            user_input=user_input, obs_type=ObservationTypes.NUMERIC_STATE
        )

    async def async_step_template(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """User flow to add a new template observation. Function name must be in the format async_step_{observation_type}."""

        return await self.step_common(
            user_input=user_input, obs_type=ObservationTypes.TEMPLATE
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Enable the reconfigure button for observations. Function name must be async_step_reconfigure to be recognised by hass."""

        sub_entry = self._get_reconfigure_subentry()

        return await self.step_common(
            user_input=user_input,
            obs_type=ObservationTypes(sub_entry.data[CONF_PLATFORM]),
            reconfiguring=True,
        )
