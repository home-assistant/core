"""Config flow for the Bayesian integration."""

from collections.abc import Mapping
from enum import StrEnum
import logging
from typing import Any, cast

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
)
from homeassistant.components.input_boolean import DOMAIN as INPUT_BOLEAN_DOMAIN
from homeassistant.components.input_number import DOMAIN as INPUT_NUMBER_DOMAIN
from homeassistant.components.number import DOMAIN as NUMBER_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.template.sensor import async_create_preview_sensor
from homeassistant.const import (
    CONF_ABOVE,
    CONF_BELOW,
    CONF_DEVICE_CLASS,
    CONF_ENTITY_ID,
    CONF_ID,
    CONF_NAME,
    CONF_PLATFORM,
    CONF_STATE,
    CONF_VALUE_TEMPLATE,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er, selector
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaCommonFlowHandler,
    SchemaConfigFlowHandler,
    SchemaFlowError,
    SchemaFlowFormStep,
    SchemaFlowMenuStep,
    SchemaFlowStep,
)
from homeassistant.helpers.template import result_as_boolean

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


class ObservationTypes(StrEnum):
    """StrEnum for all the different observation types."""

    STATE = CONF_STATE
    NUMERIC_STATE = "numeric_state"
    TEMPLATE = CONF_TEMPLATE

    @staticmethod
    def list() -> list[str]:
        """Return a list of the values."""

        return [c.value for c in ObservationTypes]


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
        vol.Required(CONF_NAME): selector.TextSelector(),
    }
)

ADD_ANOTHER_BOX_SCHEMA = vol.Schema({vol.Optional("add_another"): cv.boolean})

STATE_SUBSCHEMA = vol.Schema(
    {
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
        vol.Required(CONF_VALUE_TEMPLATE): selector.TemplateSelector(
            selector.TemplateSelectorConfig(),
        ),
    },
).extend(SUBSCHEMA_BOILERPLATE.schema)


def _convert_percentages_to_fractions(
    data: dict[str, str | float | int],
) -> dict[str, str | float]:
    """Convert percentage values in a dictionary to fractions."""
    percentages = [
        CONF_P_GIVEN_T,
        CONF_P_GIVEN_F,
        CONF_PRIOR,
        CONF_PROBABILITY_THRESHOLD,
    ]
    return {
        key: (
            value / 100
            if isinstance(value, (int, float)) and key in percentages
            else value
        )
        for key, value in data.items()
    }


def _convert_fractions_to_percentages(
    data: dict[str, str | float],
) -> dict[str, str | float]:
    """Convert fraction values in a dictionary to percentages."""
    percentages = [
        CONF_P_GIVEN_T,
        CONF_P_GIVEN_F,
        CONF_PRIOR,
        CONF_PROBABILITY_THRESHOLD,
    ]
    return {
        key: (
            value * 100
            if isinstance(value, (int, float)) and key in percentages
            else value
        )
        for key, value in data.items()
    }


async def _get_select_observation_schema(
    handler: SchemaCommonFlowHandler,
) -> vol.Schema:
    """Return schema for selecting a observation for editing."""
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
    """Return schema for observation removal."""
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
    """Choose which observation config flow step to show depending on observation type."""

    observations: list[dict[str, Any]] = user_input[CONF_OBSERVATIONS]
    selected_idx = int(user_input[CONF_INDEX])

    return str(observations[selected_idx][CONF_PLATFORM])


async def _get_state_schema(
    handler: SchemaCommonFlowHandler,
) -> vol.Schema:
    """Return the state schema, without an add_another box if editing."""

    if handler.options.get(CONF_INDEX) is None:
        return STATE_SUBSCHEMA.extend(ADD_ANOTHER_BOX_SCHEMA.schema)

    return STATE_SUBSCHEMA


async def _get_numeric_state_schema(
    handler: SchemaCommonFlowHandler,
) -> vol.Schema:
    """Return the numeric state schema, without an add_another box if editing."""

    if handler.options.get(CONF_INDEX) is None:
        return NUMERIC_STATE_SUBSCHEMA.extend(ADD_ANOTHER_BOX_SCHEMA.schema)

    return NUMERIC_STATE_SUBSCHEMA


async def _get_template_schema(
    handler: SchemaCommonFlowHandler,
) -> vol.Schema:
    """Return the template schema, without an add_another box if editing."""

    if handler.options.get(CONF_INDEX) is None:
        return TEMPLATE_SUBSCHEMA.extend(ADD_ANOTHER_BOX_SCHEMA.schema)

    return TEMPLATE_SUBSCHEMA


async def _add_more_or_end(
    user_input: dict[str, Any],
) -> ConfigFlowSteps | None:
    """Return next step_id for options flow according to template_type."""
    if user_input.get("add_another", False):
        return ConfigFlowSteps.OBSERVATION_SELECTOR
    return None


async def _get_base_suggested_values(
    handler: SchemaCommonFlowHandler,
) -> dict[str, Any]:
    """Return suggested values for the sensor base options."""

    return _convert_fractions_to_percentages(dict(handler.options))


async def _get_observation_values_if_editing(
    handler: SchemaCommonFlowHandler,
) -> dict[str, Any]:
    """Return suggested values for observation if editing."""
    if idx := handler.options.get(CONF_INDEX):
        return _convert_fractions_to_percentages(
            dict(handler.options[CONF_OBSERVATIONS][int(idx)])
        )
    return {}


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


def _validate_probabilities_given(
    user_input: dict[str, Any],
) -> None:
    """Raise errors for invalid probability_given_true/false."""
    if user_input[CONF_P_GIVEN_T] == user_input[CONF_P_GIVEN_F]:
        raise SchemaFlowError("equal_probabilities")

    if {user_input[CONF_P_GIVEN_T], user_input[CONF_P_GIVEN_F]} & {0, 100}:
        raise SchemaFlowError("extreme_prob_given_error")


async def _validate_observation_setup(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Validate observation input."""
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
        observations[int(idx)] = user_input

        # remove the index so it can not be saved
        handler.options.pop(CONF_INDEX, None)
    elif handler.parent_handler.cur_step is not None:
        # if we are in adding mode we need to record the platform from the step id
        user_input[CONF_PLATFORM] = handler.parent_handler.cur_step["step_id"]
        observations.append(user_input)
    _LOGGER.debug("Added observation with settings: %s", user_input)
    return {"add_another": True} if add_another else {}


async def _validate_remove_observation(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Delete an observation."""
    observations: list[dict[str, Any]] = handler.options[CONF_OBSERVATIONS]
    indexes: set[int] = {int(x) for x in user_input[CONF_INDEX]}

    # Standard behavior is to merge the result with the options.
    # In this case, we want to remove sub-items so we update the options directly.
    # Remove the last indexes first so subsequent items to be removed aren't shifted
    for index in sorted(indexes, reverse=True):
        observations.pop(index)
    return {}


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
        preview="template",
        validate_user_input=_validate_observation_setup,
        suggested_values=_get_observation_values_if_editing,
    ),
}

OPTIONS_FLOW: dict[str, SchemaFlowStep] = {
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

    @staticmethod
    async def async_setup_preview(hass: HomeAssistant) -> None:
        """Set up preview WS API."""
        websocket_api.async_register_command(hass, ws_start_preview)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "template/start_preview",
        vol.Required("flow_id"): str,
        vol.Required("flow_type"): vol.Any("config_flow", "options_flow"),
        vol.Required("user_input"): dict,
    }
)
@callback
def ws_start_preview(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Generate a preview."""

    def _validate(schema: vol.Schema, user_input: dict[str, Any]) -> dict:
        errors = {}
        key: vol.Marker
        for key, validator in schema.schema.items():
            if key.schema not in user_input:
                continue
            try:
                validator(user_input[key.schema])
            except vol.Invalid as ex:
                errors[key.schema] = str(ex.msg)

        return errors

    user_input: dict[str, Any] = msg["user_input"]

    entity_registry_entry: er.RegistryEntry | None = None
    if msg["flow_type"] == "config_flow":
        flow_status = hass.config_entries.flow.async_get(msg["flow_id"])
        form_step = cast(
            SchemaFlowFormStep, CONFIG_FLOW[str(ObservationTypes.TEMPLATE)]
        )
    else:
        flow_status = hass.config_entries.options.async_get(msg["flow_id"])
        form_step = cast(
            SchemaFlowFormStep, OPTIONS_FLOW[str(ObservationTypes.TEMPLATE)]
        )
        entity_registry = er.async_get(hass)
        entries = er.async_entries_for_config_entry(
            entity_registry, flow_status["handler"]
        )
        if entries:
            entity_registry_entry = entries[0]

    schema = cast(vol.Schema, form_step.schema)
    errors = _validate(schema, user_input)

    @callback
    def async_preview_updated(
        state: str | None,
        attributes: Mapping[str, Any] | None,
        listeners: dict[str, bool | set[str]] | None,
        error: str | None,
    ) -> None:
        """Forward config entry state events to websocket."""

        if error is not None:
            connection.send_message(
                websocket_api.event_message(
                    msg[CONF_ID],
                    {"error": error},
                )
            )
            return
        connection.send_message(
            websocket_api.event_message(
                msg[CONF_ID],
                {
                    "attributes": attributes,
                    "listeners": listeners,
                    "state": result_as_boolean(state),
                },
            )
        )

    if errors:
        connection.send_message(
            {
                "id": msg[CONF_ID],
                "type": websocket_api.TYPE_RESULT,
                "success": False,
                "error": {"code": "invalid_user_input", "message": errors},
            }
        )
        return

    template_config = {
        CONF_STATE: user_input[CONF_VALUE_TEMPLATE],
    }
    preview_entity = async_create_preview_sensor(hass, "Observation", template_config)
    preview_entity.hass = hass
    preview_entity.registry_entry = entity_registry_entry

    connection.send_result(msg[CONF_ID])
    connection.subscriptions[msg[CONF_ID]] = preview_entity.async_start_preview(
        async_preview_updated
    )
