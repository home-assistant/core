"""Config flow for Times of the Day integration."""

from collections.abc import Mapping
from typing import Any, cast, override

import probatio

from homeassistant.const import (
    CONF_AFTER,
    CONF_BEFORE,
    CONF_EVENT,
    CONF_NAME,
    CONF_OFFSET,
    SUN_EVENT_SUNRISE,
    SUN_EVENT_SUNSET,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import Optional, Required
from homeassistant.helpers import selector
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaCommonFlowHandler,
    SchemaConfigFlowHandler,
    SchemaFlowFormStep,
)

from .const import (
    CONF_AFTER_OFFSET,
    CONF_AFTER_TIME,
    CONF_BEFORE_OFFSET,
    CONF_BEFORE_TIME,
    CONF_TIME,
    DOMAIN,
)

CONF_AFTER_SUN = "after_sun"
CONF_BEFORE_SUN = "before_sun"

BOUNDARY_FIELDS = (
    (CONF_AFTER, CONF_AFTER_TIME, CONF_AFTER_SUN, CONF_AFTER_OFFSET),
    (CONF_BEFORE, CONF_BEFORE_TIME, CONF_BEFORE_SUN, CONF_BEFORE_OFFSET),
)


def _get_options_schema() -> probatio.Schema:
    """Build the conditional fields for each boundary."""
    schema = {}
    for boundary, time_field, sun_field, offset_field in BOUNDARY_FIELDS:
        schema.update(
            {
                probatio.Required(boundary, default=CONF_TIME): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[CONF_TIME, "sun"],
                        translation_key="boundary",
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                Required(
                    time_field, visible={"field": boundary, "value": CONF_TIME}
                ): selector.TimeSelector(),
                Required(
                    sun_field, visible={"field": boundary, "value": "sun"}
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[SUN_EVENT_SUNRISE, SUN_EVENT_SUNSET],
                        translation_key="sun_event",
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                Optional(
                    offset_field, visible={"field": boundary, "value": "sun"}
                ): selector.DurationSelector(
                    selector.DurationSelectorConfig(
                        mode=selector.DurationSelectorMode.OFFSET
                    )
                ),
            }
        )
    return probatio.Schema(schema)


OPTIONS_SCHEMA = _get_options_schema()

CONFIG_SCHEMA = probatio.Schema(
    {probatio.Required(CONF_NAME): selector.TextSelector()}
).extend(OPTIONS_SCHEMA.schema)


async def async_get_suggested_values(
    handler: SchemaCommonFlowHandler,
) -> dict[str, Any]:
    """Return the saved values for each boundary."""
    suggested_values = {}
    for key, time_field, sun_field, offset_field in BOUNDARY_FIELDS:
        boundary = handler.options[key]
        if CONF_TIME in boundary:
            suggested_values[key] = CONF_TIME
            suggested_values[time_field] = boundary[CONF_TIME]
        else:
            suggested_values[key] = "sun"
            suggested_values[sun_field] = boundary[CONF_EVENT]
            if CONF_OFFSET in boundary:
                suggested_values[offset_field] = boundary[CONF_OFFSET]
    return suggested_values


async def async_normalize_user_input(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Store visible fields in the config entry's boundary format."""
    for key, time_field, sun_field, offset_field in BOUNDARY_FIELDS:
        if user_input[key] == CONF_TIME:
            user_input[key] = {CONF_TIME: user_input.pop(time_field)}
        else:
            boundary = {CONF_EVENT: user_input.pop(sun_field)}
            if offset_field in user_input:
                boundary[CONF_OFFSET] = user_input.pop(offset_field)
            user_input[key] = boundary
    return user_input


CONFIG_FLOW = {
    "user": SchemaFlowFormStep(
        CONFIG_SCHEMA, validate_user_input=async_normalize_user_input
    ),
}

OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(
        OPTIONS_SCHEMA,
        validate_user_input=async_normalize_user_input,
        suggested_values=async_get_suggested_values,
    ),
}


class ConfigFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle a config or options flow for Times of the Day."""

    VERSION = 2

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW
    options_flow_reloads = True

    @callback
    @override
    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""
        return cast(str, options["name"])
