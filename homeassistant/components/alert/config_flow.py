"""Config flow for the Alert integration."""

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
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaCommonFlowHandler,
    SchemaConfigFlowHandler,
    SchemaFlowError,
    SchemaFlowFormStep,
)
from homeassistant.helpers.selector import (
    BooleanSelector,
    EntitySelector,
    ObjectSelector,
    TemplateSelector,
    TextSelector,
    TextSelectorConfig,
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

MIN_REPEAT_MINUTES = 1 / 60


async def _validate_repeat(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Validate that repeat entries are floats above the minimum delay."""
    raw_values = user_input.get(CONF_REPEAT)
    if not raw_values:
        raise SchemaFlowError("repeat_required")

    parsed: list[float] = []
    for value in raw_values:
        try:
            number = float(value)
        except (TypeError, ValueError) as err:
            raise SchemaFlowError("invalid_repeat") from err
        if number < MIN_REPEAT_MINUTES:
            raise SchemaFlowError("invalid_repeat")
        parsed.append(number)

    return {**user_input, CONF_REPEAT: parsed}


OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ENTITY_ID): EntitySelector(),
        vol.Required(CONF_STATE, default=STATE_ON): TextSelector(),
        vol.Required(CONF_REPEAT): TextSelector(TextSelectorConfig(multiple=True)),
        vol.Required(CONF_CAN_ACK, default=DEFAULT_CAN_ACK): BooleanSelector(),
        vol.Required(CONF_SKIP_FIRST, default=DEFAULT_SKIP_FIRST): BooleanSelector(),
        vol.Optional(CONF_NOTIFIERS, default=list): TextSelector(
            TextSelectorConfig(multiple=True)
        ),
        vol.Optional(CONF_TITLE): TemplateSelector(),
        vol.Optional(CONF_ALERT_MESSAGE): TemplateSelector(),
        vol.Optional(CONF_DONE_MESSAGE): TemplateSelector(),
        vol.Optional(CONF_DATA): ObjectSelector(),
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): TextSelector(),
    }
).extend(OPTIONS_SCHEMA.schema)

CONFIG_FLOW = {
    "user": SchemaFlowFormStep(CONFIG_SCHEMA, validate_user_input=_validate_repeat),
}

OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(OPTIONS_SCHEMA, validate_user_input=_validate_repeat),
}


class AlertConfigFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle a config or options flow for Alert."""

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW
    options_flow_reloads = True

    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""
        return cast(str, options[CONF_NAME])
