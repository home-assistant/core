"""Config flow for Manual Alarm component."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

import voluptuous as vol

from homeassistant.const import (
    CONF_ARMING_TIME,
    CONF_CODE,
    CONF_DELAY_TIME,
    CONF_DISARM_AFTER_TRIGGER,
    CONF_NAME,
    CONF_TRIGGER_TIME,
)
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaCommonFlowHandler,
    SchemaConfigFlowHandler,
    SchemaFlowFormStep,
)
from homeassistant.helpers.selector import (
    BooleanSelector,
    DurationSelector,
    DurationSelectorConfig,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)

from .const import (
    CONF_ARMING_STATES,
    CONF_CODE_ARM_REQUIRED,
    DEFAULT_ALARM_NAME,
    DEFAULT_ARMING_TIME,
    DEFAULT_DELAY_TIME,
    DEFAULT_DISARM_AFTER_TRIGGER,
    DEFAULT_TRIGGER_TIME,
    DOMAIN,
    SUPPORTED_ARMING_STATES,
    SUPPORTED_PRETRIGGER_STATES,
    SUPPORTED_STATES,
)


async def get_state_specific_schema(
    handler: SchemaCommonFlowHandler,
) -> vol.Schema | None:
    """Get state specific schema."""
    schema = {}
    selector = DurationSelector(DurationSelectorConfig(allow_negative=False))

    for state in SUPPORTED_STATES:
        if (
            state in SUPPORTED_ARMING_STATES
            and state not in handler.options[CONF_ARMING_STATES]
        ):
            # Skip states that are not enabled
            continue
        if state in SUPPORTED_PRETRIGGER_STATES:
            schema[vol.Optional(f"{state}_{CONF_DELAY_TIME}")] = selector

            schema[vol.Optional(f"{state}_{CONF_TRIGGER_TIME}")] = selector

        if state in SUPPORTED_ARMING_STATES:
            schema[vol.Optional(f"{state}_{CONF_ARMING_TIME}")] = selector

    return vol.Schema(schema)


DATA_SCHEMA_OPTIONS = vol.Schema(
    {
        vol.Optional(CONF_CODE): TextSelector(),
        vol.Optional(CONF_CODE_ARM_REQUIRED, default=True): BooleanSelector(),
        vol.Optional(
            CONF_DELAY_TIME, default={"seconds": DEFAULT_DELAY_TIME.total_seconds()}
        ): DurationSelector(DurationSelectorConfig(allow_negative=False)),
        vol.Optional(
            CONF_ARMING_TIME, default={"seconds": DEFAULT_ARMING_TIME.total_seconds()}
        ): DurationSelector(DurationSelectorConfig(allow_negative=False)),
        vol.Optional(
            CONF_TRIGGER_TIME, default={"seconds": DEFAULT_TRIGGER_TIME.total_seconds()}
        ): DurationSelector(DurationSelectorConfig(allow_negative=False)),
        vol.Optional(
            CONF_DISARM_AFTER_TRIGGER, default=DEFAULT_DISARM_AFTER_TRIGGER
        ): BooleanSelector(),
        vol.Optional(
            CONF_ARMING_STATES, default=SUPPORTED_ARMING_STATES
        ): SelectSelector(
            SelectSelectorConfig(
                options=SUPPORTED_ARMING_STATES,
                multiple=True,
                mode=SelectSelectorMode.DROPDOWN,
                translation_key="arming_states",
            ),
        ),
    }
)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME, default=DEFAULT_ALARM_NAME): TextSelector(),
    }
)

CONFIG_FLOW = {
    "user": SchemaFlowFormStep(
        schema=DATA_SCHEMA.extend(DATA_SCHEMA_OPTIONS.schema),
        next_step="state_specific",
    ),
    "state_specific": SchemaFlowFormStep(
        schema=get_state_specific_schema,
    ),
}
OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(
        DATA_SCHEMA_OPTIONS,
        next_step="state_specific",
    ),
    "state_specific": SchemaFlowFormStep(
        schema=get_state_specific_schema,
    ),
}


class ManualConfigFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle a config flow for Manual alarm."""

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW

    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""
        return cast(str, options[CONF_NAME])
