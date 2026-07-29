"""Config flow for Times of the Day integration."""

from collections.abc import Mapping
from typing import Any, cast, override

import voluptuous as vol

from homeassistant.const import CONF_NAME, SUN_EVENT_SUNRISE, SUN_EVENT_SUNSET
from homeassistant.helpers import selector
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaCommonFlowHandler,
    SchemaConfigFlowHandler,
    SchemaFlowError,
    SchemaFlowFormStep,
)

from .const import CONF_AFTER_TIME, CONF_BEFORE_TIME, DOMAIN

CONF_AFTER_MODE = "after_mode"
CONF_BEFORE_MODE = "before_mode"

MODE_TIME = "time"
MODE_OPTIONS = [MODE_TIME, SUN_EVENT_SUNRISE, SUN_EVENT_SUNSET]

MODE_SELECTOR = selector.SelectSelector(
    selector.SelectSelectorConfig(
        options=MODE_OPTIONS,
        mode=selector.SelectSelectorMode.DROPDOWN,
        translation_key="tod_mode",
    )
)

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_AFTER_MODE, default=MODE_TIME): MODE_SELECTOR,
        vol.Optional(CONF_AFTER_TIME): selector.TimeSelector(),
        vol.Required(CONF_BEFORE_MODE, default=MODE_TIME): MODE_SELECTOR,
        vol.Optional(CONF_BEFORE_TIME): selector.TimeSelector(),
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): selector.TextSelector(),
    }
).extend(OPTIONS_SCHEMA.schema)


async def _validate_after_before(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Resolve the after/before mode and time fields to a single stored value."""
    for mode_key, time_key in (
        (CONF_AFTER_MODE, CONF_AFTER_TIME),
        (CONF_BEFORE_MODE, CONF_BEFORE_TIME),
    ):
        mode = user_input.pop(mode_key)
        time_value = user_input.pop(time_key, None)
        if mode == MODE_TIME:
            if time_value is None:
                raise SchemaFlowError(f"{time_key}_required")
            user_input[time_key] = time_value
        else:
            user_input[time_key] = mode
    return user_input


async def _suggested_values(handler: SchemaCommonFlowHandler) -> dict[str, Any]:
    """Split the stored after/before value into its mode and time fields."""
    suggested_values = dict(handler.options)
    for mode_key, time_key in (
        (CONF_AFTER_MODE, CONF_AFTER_TIME),
        (CONF_BEFORE_MODE, CONF_BEFORE_TIME),
    ):
        if (time_value := suggested_values.get(time_key)) is None:
            continue
        if time_value in (SUN_EVENT_SUNRISE, SUN_EVENT_SUNSET):
            suggested_values[mode_key] = time_value
            del suggested_values[time_key]
        else:
            suggested_values[mode_key] = MODE_TIME
    return suggested_values


CONFIG_FLOW = {
    "user": SchemaFlowFormStep(
        CONFIG_SCHEMA,
        validate_user_input=_validate_after_before,
        suggested_values=_suggested_values,
    ),
}

OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(
        OPTIONS_SCHEMA,
        validate_user_input=_validate_after_before,
        suggested_values=_suggested_values,
    ),
}


class ConfigFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle a config or options flow for Times of the Day."""

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW
    options_flow_reloads = True

    @override
    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""
        return cast(str, options["name"])
