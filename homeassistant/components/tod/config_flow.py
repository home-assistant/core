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
from homeassistant.helpers import selector
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaCommonFlowHandler,
    SchemaConfigFlowHandler,
    SchemaFlowFormStep,
)

from .const import CONF_TIME, DOMAIN

TRANSITION_SELECTOR = selector.ChooseSelector(
    selector.ChooseSelectorConfig(
        translation_key="transition",
        choices={
            "time": {"selector": {"time": {}}},
            "sun": {
                "selector": {
                    "object": {
                        "translation_key": "transition",
                        "fields": {
                            CONF_EVENT: {
                                "required": True,
                                "selector": {
                                    "select": {
                                        "options": [
                                            SUN_EVENT_SUNRISE,
                                            SUN_EVENT_SUNSET,
                                        ],
                                        "translation_key": "sun_event",
                                        "mode": selector.SelectSelectorMode.DROPDOWN,
                                    }
                                },
                            },
                            CONF_OFFSET: {
                                "selector": {
                                    "duration": {
                                        "mode": selector.DurationSelectorMode.OFFSET
                                    }
                                }
                            },
                        },
                    }
                }
            },
        },
    )
)

OPTIONS_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_AFTER): TRANSITION_SELECTOR,
        probatio.Required(CONF_BEFORE): TRANSITION_SELECTOR,
    }
)

CONFIG_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_NAME): selector.TextSelector(),
    }
).extend(OPTIONS_SCHEMA.schema)


async def async_get_suggested_values(
    handler: SchemaCommonFlowHandler,
) -> dict[str, Any]:
    """Return the saved values for each transition selector."""
    suggested_values = {}
    for key in (CONF_AFTER, CONF_BEFORE):
        transition = handler.options[key]
        suggested_values[key] = transition.get(CONF_TIME, transition)
    return suggested_values


async def async_get_options_schema(
    handler: SchemaCommonFlowHandler,
) -> probatio.Schema:
    """Put the saved choice first so the frontend initializes it."""
    choices = TRANSITION_SELECTOR.config["choices"]
    schema = {}
    for key in (CONF_AFTER, CONF_BEFORE):
        choice = "time" if CONF_TIME in handler.options[key] else "sun"
        schema[probatio.Required(key)] = selector.ChooseSelector(
            selector.ChooseSelectorConfig(
                translation_key="transition",
                choices={choice: choices[choice], **choices},
            )
        )
    return probatio.Schema(schema)


async def async_normalize_user_input(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Store fixed times in the config entry's transition format."""
    for key in (CONF_AFTER, CONF_BEFORE):
        if isinstance(transition := user_input[key], str):
            user_input[key] = {CONF_TIME: transition}
    return user_input


CONFIG_FLOW = {
    "user": SchemaFlowFormStep(
        CONFIG_SCHEMA, validate_user_input=async_normalize_user_input
    ),
}

OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(
        async_get_options_schema,
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
