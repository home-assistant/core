"""Config flow for Wake on lan integration."""

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.const import CONF_BROADCAST_ADDRESS, CONF_BROADCAST_PORT, CONF_MAC
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaCommonFlowHandler,
    SchemaConfigFlowHandler,
    SchemaFlowFormStep,
)
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
)

from .const import DEFAULT_NAME, DOMAIN


async def validate(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Validate input setup."""
    user_input = await validate_options(handler, user_input)

    user_input[CONF_MAC] = dr.format_mac(user_input[CONF_MAC])

    # Mac address needs to be unique
    handler.parent_handler._async_abort_entries_match({CONF_MAC: user_input[CONF_MAC]})  # noqa: SLF001

    return user_input


async def validate_options(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Validate input options."""
    if CONF_BROADCAST_PORT in user_input:
        # Convert float to int for broadcast port
        user_input[CONF_BROADCAST_PORT] = int(user_input[CONF_BROADCAST_PORT])
    return user_input


DATA_SCHEMA = {vol.Required(CONF_MAC): TextSelector()}
OPTIONS_SCHEMA = {
    vol.Optional(CONF_BROADCAST_ADDRESS): TextSelector(),
    vol.Optional(CONF_BROADCAST_PORT): NumberSelector(
        NumberSelectorConfig(min=0, max=65535, step=1, mode=NumberSelectorMode.BOX)
    ),
}


CONFIG_FLOW = {
    "user": SchemaFlowFormStep(
        schema=vol.Schema(DATA_SCHEMA).extend(OPTIONS_SCHEMA),
        validate_user_input=validate,
    )
}
OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(
        vol.Schema(OPTIONS_SCHEMA), validate_user_input=validate_options
    ),
}


class WakeonLanConfigFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle a config flow for Wake on Lan."""

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW

    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""
        mac: str = options[CONF_MAC]
        return f"{DEFAULT_NAME} {mac}"
