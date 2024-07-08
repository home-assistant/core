"""Config flow for filter."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

import voluptuous as vol

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import CONF_ENTITY_ID, CONF_NAME
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaCommonFlowHandler,
    SchemaConfigFlowHandler,
    SchemaFlowFormStep,
)
from homeassistant.helpers.selector import (
    DurationSelector,
    DurationSelectorConfig,
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    Selector,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)

from .const import (
    CONF_FILTER_LOWER_BOUND,
    CONF_FILTER_NAME,
    CONF_FILTER_PRECISION,
    CONF_FILTER_RADIUS,
    CONF_FILTER_TIME_CONSTANT,
    CONF_FILTER_UPPER_BOUND,
    CONF_FILTER_WINDOW_SIZE,
    CONF_TIME_SMA_TYPE,
    DEFAULT_FILTER_RADIUS,
    DEFAULT_FILTER_TIME_CONSTANT,
    DEFAULT_NAME,
    DEFAULT_PRECISION,
    DEFAULT_WINDOW_SIZE,
    DOMAIN,
    FILTER_NAME_LOWPASS,
    FILTER_NAME_OUTLIER,
    FILTER_NAME_RANGE,
    FILTER_NAME_THROTTLE,
    FILTER_NAME_TIME_SMA,
    FILTER_NAME_TIME_THROTTLE,
    TIME_SMA_LAST,
)

FILTERS = [
    FILTER_NAME_LOWPASS,
    FILTER_NAME_OUTLIER,
    FILTER_NAME_RANGE,
    FILTER_NAME_THROTTLE,
    FILTER_NAME_TIME_SMA,
    FILTER_NAME_TIME_THROTTLE,
]


async def get_options_schema(handler: SchemaCommonFlowHandler) -> vol.Schema:
    """Return schema for options."""
    filter_schema: dict[vol.Marker, Selector] = {}

    if handler.options[CONF_FILTER_NAME] == FILTER_NAME_OUTLIER:
        filter_schema = {
            vol.Optional(
                CONF_FILTER_WINDOW_SIZE, default=DEFAULT_WINDOW_SIZE
            ): NumberSelector(
                NumberSelectorConfig(min=0, step=1, mode=NumberSelectorMode.BOX)
            ),
            vol.Optional(
                CONF_FILTER_RADIUS, default=DEFAULT_FILTER_RADIUS
            ): NumberSelector(
                NumberSelectorConfig(min=0, step=1, mode=NumberSelectorMode.BOX)
            ),
        }

    elif handler.options[CONF_FILTER_NAME] == FILTER_NAME_LOWPASS:
        filter_schema = {
            vol.Optional(
                CONF_FILTER_WINDOW_SIZE, default=DEFAULT_WINDOW_SIZE
            ): NumberSelector(
                NumberSelectorConfig(min=0, step=1, mode=NumberSelectorMode.BOX)
            ),
            vol.Optional(
                CONF_FILTER_TIME_CONSTANT, default=DEFAULT_FILTER_TIME_CONSTANT
            ): NumberSelector(
                NumberSelectorConfig(min=0, step=1, mode=NumberSelectorMode.BOX)
            ),
        }

    elif handler.options[CONF_FILTER_NAME] == FILTER_NAME_RANGE:
        filter_schema = {
            vol.Optional(CONF_FILTER_LOWER_BOUND): NumberSelector(
                NumberSelectorConfig(min=0, step=1, mode=NumberSelectorMode.BOX)
            ),
            vol.Optional(CONF_FILTER_UPPER_BOUND): NumberSelector(
                NumberSelectorConfig(min=0, step=1, mode=NumberSelectorMode.BOX)
            ),
        }

    elif handler.options[CONF_FILTER_NAME] == FILTER_NAME_TIME_SMA:
        filter_schema = {
            vol.Optional(CONF_TIME_SMA_TYPE, default=TIME_SMA_LAST): SelectSelector(
                SelectSelectorConfig(
                    options=[TIME_SMA_LAST],
                    mode=SelectSelectorMode.DROPDOWN,
                    translation_key=CONF_TIME_SMA_TYPE,
                )
            ),
            vol.Required(CONF_FILTER_WINDOW_SIZE): DurationSelector(
                DurationSelectorConfig(enable_day=False, allow_negative=False)
            ),
        }

    elif handler.options[CONF_FILTER_NAME] == FILTER_NAME_THROTTLE:
        filter_schema = {
            vol.Optional(
                CONF_FILTER_WINDOW_SIZE, default=DEFAULT_WINDOW_SIZE
            ): NumberSelector(
                NumberSelectorConfig(min=0, step=1, mode=NumberSelectorMode.BOX)
            ),
        }

    elif handler.options[CONF_FILTER_NAME] == FILTER_NAME_TIME_THROTTLE:
        filter_schema = {
            vol.Required(CONF_FILTER_WINDOW_SIZE): DurationSelector(
                DurationSelectorConfig(enable_day=False, allow_negative=False)
            ),
        }

    base_schema: dict[vol.Marker, Selector] = {
        vol.Optional(CONF_FILTER_PRECISION, default=DEFAULT_PRECISION): NumberSelector(
            NumberSelectorConfig(min=0, step=1, mode=NumberSelectorMode.BOX)
        )
    }

    return vol.Schema({**filter_schema, **base_schema})


async def validate_options(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Validate options selected."""

    if CONF_FILTER_WINDOW_SIZE in user_input and isinstance(
        user_input[CONF_FILTER_WINDOW_SIZE], float
    ):
        user_input[CONF_FILTER_WINDOW_SIZE] = int(user_input[CONF_FILTER_WINDOW_SIZE])
    if CONF_FILTER_TIME_CONSTANT in user_input:
        user_input[CONF_FILTER_TIME_CONSTANT] = int(
            user_input[CONF_FILTER_TIME_CONSTANT]
        )
    if CONF_FILTER_PRECISION in user_input:
        user_input[CONF_FILTER_PRECISION] = int(user_input[CONF_FILTER_PRECISION])

    handler.parent_handler._async_abort_entries_match({**handler.options, **user_input})  # noqa: SLF001

    return user_input


DATA_SCHEMA_SETUP = vol.Schema(
    {
        vol.Required(CONF_NAME, default=DEFAULT_NAME): TextSelector(),
        vol.Required(CONF_ENTITY_ID): EntitySelector(
            EntitySelectorConfig(domain=[SENSOR_DOMAIN])
        ),
        vol.Required(CONF_FILTER_NAME): SelectSelector(
            SelectSelectorConfig(
                options=FILTERS,
                mode=SelectSelectorMode.DROPDOWN,
                translation_key=CONF_FILTER_NAME,
            )
        ),
    }
)


CONFIG_FLOW = {
    "user": SchemaFlowFormStep(
        schema=DATA_SCHEMA_SETUP,
        next_step="options",
    ),
    "options": SchemaFlowFormStep(
        schema=get_options_schema,
        validate_user_input=validate_options,
    ),
}
OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(
        get_options_schema,
        validate_user_input=validate_options,
    ),
}


class FilterConfigFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle a config flow for Filter."""

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW

    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""
        return cast(str, options[CONF_NAME])
