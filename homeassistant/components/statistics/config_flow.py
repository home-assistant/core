"""Config flow for statistics."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

import voluptuous as vol

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import CONF_ENTITY_ID, CONF_NAME
from homeassistant.core import split_entity_id
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaCommonFlowHandler,
    SchemaConfigFlowHandler,
    SchemaFlowError,
    SchemaFlowFormStep,
)
from homeassistant.helpers.selector import (
    BooleanSelector,
    DurationSelector,
    DurationSelectorConfig,
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)

from . import DOMAIN
from .sensor import (
    CONF_KEEP_LAST_SAMPLE,
    CONF_MAX_AGE,
    CONF_PERCENTILE,
    CONF_PRECISION,
    CONF_SAMPLES_MAX_BUFFER_SIZE,
    CONF_STATE_CHARACTERISTIC,
    DEFAULT_NAME,
    DEFAULT_PRECISION,
    STATS_BINARY_SUPPORT,
    STATS_NUMERIC_SUPPORT,
)


async def get_state_characteristics(handler: SchemaCommonFlowHandler) -> vol.Schema:
    """Return schema with state characteristics."""
    is_binary = (
        split_entity_id(handler.options[CONF_ENTITY_ID])[0] == BINARY_SENSOR_DOMAIN
    )
    if is_binary:
        options = STATS_BINARY_SUPPORT
    else:
        options = STATS_NUMERIC_SUPPORT

    return vol.Schema(
        {
            vol.Required(CONF_STATE_CHARACTERISTIC): SelectSelector(
                SelectSelectorConfig(
                    options=list(options),
                    translation_key=CONF_STATE_CHARACTERISTIC,
                    sort=True,
                    mode=SelectSelectorMode.DROPDOWN,
                )
            ),
        }
    )


async def validate_options(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Validate options selected."""
    if (
        user_input.get(CONF_SAMPLES_MAX_BUFFER_SIZE) is None
        and user_input.get(CONF_MAX_AGE) is None
    ):
        raise SchemaFlowError("missing_max_age_or_sampling_size")

    if (
        user_input.get(CONF_KEEP_LAST_SAMPLE) is True
        and user_input.get(CONF_MAX_AGE) is None
    ):
        raise SchemaFlowError("missing_keep_last_sample")

    handler.parent_handler._async_abort_entries_match({**handler.options, **user_input})  # noqa: SLF001

    return user_input


DATA_SCHEMA_SETUP = vol.Schema(
    {
        vol.Required(CONF_NAME, default=DEFAULT_NAME): TextSelector(),
        vol.Required(CONF_ENTITY_ID): EntitySelector(
            EntitySelectorConfig(domain=[BINARY_SENSOR_DOMAIN, SENSOR_DOMAIN])
        ),
    }
)
DATA_SCHEMA_OPTIONS = vol.Schema(
    {
        vol.Optional(CONF_SAMPLES_MAX_BUFFER_SIZE): NumberSelector(
            NumberSelectorConfig(min=0, step=1, mode=NumberSelectorMode.BOX)
        ),
        vol.Optional(CONF_MAX_AGE): DurationSelector(
            DurationSelectorConfig(enable_day=False, allow_negative=False)
        ),
        vol.Optional(CONF_KEEP_LAST_SAMPLE, default=False): BooleanSelector(),
        vol.Optional(CONF_PERCENTILE, default=50): NumberSelector(
            NumberSelectorConfig(min=1, max=99, step=1, mode=NumberSelectorMode.BOX)
        ),
        vol.Optional(CONF_PRECISION, default=DEFAULT_PRECISION): NumberSelector(
            NumberSelectorConfig(min=0, step=1, mode=NumberSelectorMode.BOX)
        ),
    }
)

CONFIG_FLOW = {
    "user": SchemaFlowFormStep(
        schema=DATA_SCHEMA_SETUP,
        next_step="state_characteristic",
    ),
    "state_characteristic": SchemaFlowFormStep(
        schema=get_state_characteristics, next_step="options"
    ),
    "options": SchemaFlowFormStep(
        schema=DATA_SCHEMA_OPTIONS,
        validate_user_input=validate_options,
    ),
}
OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(
        DATA_SCHEMA_OPTIONS,
        validate_user_input=validate_options,
    ),
}


class StatisticsConfigFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle a config flow for Statistics."""

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW

    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""
        return cast(str, options[CONF_NAME])
