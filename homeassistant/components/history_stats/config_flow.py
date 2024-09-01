"""The history_stats component config flow."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

import voluptuous as vol

from homeassistant.const import CONF_ENTITY_ID, CONF_NAME, CONF_STATE, CONF_TYPE
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaCommonFlowHandler,
    SchemaConfigFlowHandler,
    SchemaFlowError,
    SchemaFlowFormStep,
)
from homeassistant.helpers.selector import (
    DurationSelector,
    DurationSelectorConfig,
    EntitySelector,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TemplateSelector,
    TextSelector,
    TextSelectorConfig,
)

from .const import (
    CONF_DURATION,
    CONF_END,
    CONF_PERIOD_KEYS,
    CONF_START,
    CONF_TYPE_KEYS,
    CONF_TYPE_TIME,
    DEFAULT_NAME,
    DOMAIN,
)


async def validate_options(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Validate options selected."""
    if sum(param in user_input for param in CONF_PERIOD_KEYS) != 2:
        raise SchemaFlowError("only_two_keys_allowed")

    handler.parent_handler._async_abort_entries_match({**handler.options, **user_input})  # noqa: SLF001

    return user_input


DATA_SCHEMA_SETUP = vol.Schema(
    {
        vol.Required(CONF_NAME, default=DEFAULT_NAME): TextSelector(),
        vol.Required(CONF_ENTITY_ID): EntitySelector(),
        vol.Required(CONF_STATE): TextSelector(TextSelectorConfig(multiple=True)),
        vol.Required(CONF_TYPE, default=CONF_TYPE_TIME): SelectSelector(
            SelectSelectorConfig(
                options=CONF_TYPE_KEYS,
                mode=SelectSelectorMode.DROPDOWN,
                translation_key=CONF_TYPE,
            )
        ),
    }
)
DATA_SCHEMA_OPTIONS = vol.Schema(
    {
        vol.Optional(CONF_START): TemplateSelector(),
        vol.Optional(CONF_END): TemplateSelector(),
        vol.Optional(CONF_DURATION): DurationSelector(
            DurationSelectorConfig(enable_day=True, allow_negative=False)
        ),
    }
)

CONFIG_FLOW = {
    "user": SchemaFlowFormStep(
        schema=DATA_SCHEMA_SETUP,
        next_step="options",
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
    """Handle a config flow for History stats."""

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW

    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""
        return cast(str, options[CONF_NAME])
