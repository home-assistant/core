"""Config flow for the manual alarm control panel integration."""

from collections.abc import Mapping
from typing import Any, override

import probatio

from homeassistant.components.alarm_control_panel import AlarmControlPanelState
from homeassistant.const import (
    CONF_ARMING_TIME,
    CONF_CODE,
    CONF_DELAY_TIME,
    CONF_DISARM_AFTER_TRIGGER,
    CONF_NAME,
    CONF_TRIGGER_TIME,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import section
from homeassistant.helpers import selector
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaCommonFlowHandler,
    SchemaConfigFlowHandler,
    SchemaFlowError,
    SchemaFlowFormStep,
)

from .const import (
    CONF_ARMING_STATES,
    CONF_CODE_ARM_REQUIRED,
    CONF_CODE_TEMPLATE,
    DEFAULT_ARMING_TIME,
    DEFAULT_DELAY_TIME,
    DEFAULT_DISARM_AFTER_TRIGGER,
    DEFAULT_TRIGGER_TIME,
    DOMAIN,
    SUPPORTED_ARMING_STATES,
)

DURATION_SELECTOR = selector.DurationSelector(
    selector.DurationSelectorConfig(allow_negative=False)
)


def _state_section(state: AlarmControlPanelState) -> section:
    """Return a collapsed section with the per-state timing overrides."""
    schema: dict[probatio.Optional, selector.DurationSelector] = {
        probatio.Optional(CONF_DELAY_TIME): DURATION_SELECTOR,
        probatio.Optional(CONF_TRIGGER_TIME): DURATION_SELECTOR,
    }
    if state in SUPPORTED_ARMING_STATES:
        schema[probatio.Optional(CONF_ARMING_TIME)] = DURATION_SELECTOR
    return section(probatio.Schema(schema), {"collapsed": True})


async def _validate_code(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Validate that not both a code and a code template are set."""
    if CONF_CODE in user_input and CONF_CODE_TEMPLATE in user_input:
        raise SchemaFlowError("code_and_code_template")
    return user_input


OPTIONS_SCHEMA = probatio.Schema(
    {
        probatio.Optional(CONF_CODE): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
        ),
        probatio.Optional(CONF_CODE_TEMPLATE): selector.TemplateSelector(),
        probatio.Required(
            CONF_CODE_ARM_REQUIRED, default=True
        ): selector.BooleanSelector(),
        probatio.Required(
            CONF_ARMING_STATES, default=list(SUPPORTED_ARMING_STATES)
        ): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=list(SUPPORTED_ARMING_STATES),
                multiple=True,
                translation_key=CONF_ARMING_STATES,
            )
        ),
        probatio.Required(
            CONF_ARMING_TIME,
            default={"seconds": int(DEFAULT_ARMING_TIME.total_seconds())},
        ): DURATION_SELECTOR,
        probatio.Required(
            CONF_DELAY_TIME,
            default={"seconds": int(DEFAULT_DELAY_TIME.total_seconds())},
        ): DURATION_SELECTOR,
        probatio.Required(
            CONF_TRIGGER_TIME,
            default={"seconds": int(DEFAULT_TRIGGER_TIME.total_seconds())},
        ): DURATION_SELECTOR,
        probatio.Required(
            CONF_DISARM_AFTER_TRIGGER, default=DEFAULT_DISARM_AFTER_TRIGGER
        ): selector.BooleanSelector(),
        **{
            probatio.Optional(state): _state_section(state)
            for state in (AlarmControlPanelState.DISARMED, *SUPPORTED_ARMING_STATES)
        },
    }
)

CONFIG_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_NAME): selector.TextSelector(),
    }
).extend(OPTIONS_SCHEMA.schema)

CONFIG_FLOW = {
    "user": SchemaFlowFormStep(CONFIG_SCHEMA, validate_user_input=_validate_code)
}

OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(OPTIONS_SCHEMA, validate_user_input=_validate_code)
}


class ConfigFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle a config or options flow for the manual alarm control panel."""

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW
    options_flow_reloads = True

    @callback
    @override
    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""
        name: str = options[CONF_NAME]
        return name
