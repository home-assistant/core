"""Config flow for Ping (ICMP) integration."""
from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any, cast

import voluptuous as vol

from homeassistant.const import CONF_HOST
from homeassistant.helpers import selector
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaConfigFlowHandler,
    SchemaFlowFormStep,
)

from .const import CONF_PING_COUNT, DEFAULT_PING_COUNT, DOMAIN

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(
            CONF_PING_COUNT, default=DEFAULT_PING_COUNT
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=1, max=100, mode=selector.NumberSelectorMode.BOX
            )
        ),
    }
)

CONFIG_FLOW = {"user": SchemaFlowFormStep(CONFIG_SCHEMA)}

OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(CONFIG_SCHEMA),
}


class ConfigFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle a config or options flow for Ping."""

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW

    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""
        return cast(str, options[CONF_HOST])
