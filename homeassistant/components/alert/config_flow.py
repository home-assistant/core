"""Config flow for Alert integration."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

import voluptuous as vol

from homeassistant.const import (
    CONF_ENTITY_ID,
    CONF_NAME,
    CONF_REPEAT,
    CONF_STATE,
    STATE_ON,
)
from homeassistant.helpers import selector
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaConfigFlowHandler,
    SchemaFlowError,
    SchemaFlowFormStep,
    SchemaFlowMenuStep,
)

from .const import (
    CONF_ALERT_MESSAGE,
    CONF_CAN_ACK,
    CONF_DATA,
    CONF_DONE_MESSAGE,
    CONF_NOTIFIERS,
    CONF_SKIP_FIRST,
    CONF_TITLE,
    DEFAULT_CAN_ACK,
    DEFAULT_SKIP_FIRST,
    DOMAIN,
)

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_STATE, default=STATE_ON): selector.TextSelector(),
        vol.Required(CONF_REPEAT): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[],
                multiple=True,
                custom_value=True,
                mode=selector.SelectSelectorMode.DROPDOWN,
            )
        ),
        vol.Required(CONF_CAN_ACK, default=DEFAULT_CAN_ACK): selector.BooleanSelector(),
        vol.Required(
            CONF_SKIP_FIRST, default=DEFAULT_SKIP_FIRST
        ): selector.BooleanSelector(),
        vol.Optional(CONF_ALERT_MESSAGE): selector.TemplateSelector(),
        vol.Optional(CONF_DONE_MESSAGE): selector.TemplateSelector(),
        vol.Optional(CONF_TITLE): selector.TemplateSelector(),
        vol.Optional(CONF_DATA): selector.ObjectSelector(),
        vol.Required(CONF_NOTIFIERS): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="notify", multiple=True)
        ),
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): selector.TextSelector(),
        vol.Required(CONF_ENTITY_ID): selector.EntitySelector(),
    }
).extend(OPTIONS_SCHEMA.schema)


def validate_input(user_input: dict[str, Any]) -> dict[str, Any]:
    """Validate user input."""
    try:
        number_list = []
        if isinstance(user_input[CONF_REPEAT], list):
            for number_string in user_input[CONF_REPEAT]:
                new_number = float(number_string)
                number_list.append(new_number)
        if isinstance(user_input[CONF_REPEAT], str):
            new_number = float(user_input[CONF_REPEAT])
            number_list.append(new_number)
    except ValueError as error:
        raise SchemaFlowError("repeat_error") from error

    user_input[CONF_REPEAT] = number_list
    return user_input


CONFIG_FLOW: dict[str, SchemaFlowFormStep | SchemaFlowMenuStep] = {
    "user": SchemaFlowFormStep(CONFIG_SCHEMA, validate_input)
}

OPTIONS_FLOW: dict[str, SchemaFlowFormStep | SchemaFlowMenuStep] = {
    "init": SchemaFlowFormStep(OPTIONS_SCHEMA)
}


class ConfigFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle a config or options flow for Alert."""

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW

    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""
        return cast(str, options["name"]) if "name" in options else ""
