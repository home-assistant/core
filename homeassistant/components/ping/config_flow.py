"""Config flow for Ping (ICMP) integration."""
from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any, cast

import voluptuous as vol

from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaConfigFlowHandler,
    SchemaFlowFormStep,
)

from .const import CONF_IMPORTED_BY, CONF_PING_COUNT, DEFAULT_PING_COUNT, DOMAIN

_LOGGER = logging.getLogger(__name__)


OPTIONS_SCHEMA = vol.Schema(
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


CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): selector.TextSelector(),
    }
).extend(OPTIONS_SCHEMA.schema)

CONFIG_FLOW = {"user": SchemaFlowFormStep(CONFIG_SCHEMA)}

OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(OPTIONS_SCHEMA),
}


class ConfigFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle a config or options flow for Ping."""

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW

    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""
        return cast(str, options[CONF_NAME])

    async def async_step_import(self, import_info: Mapping[str, Any]) -> FlowResult:
        """Import an entry."""

        to_import = {
            CONF_NAME: import_info[CONF_NAME],
            CONF_HOST: import_info[CONF_HOST],
            CONF_PING_COUNT: import_info[CONF_PING_COUNT],
            CONF_IMPORTED_BY: import_info[CONF_IMPORTED_BY],
        }

        # remove existing entry when user updated it in configuration.yaml
        if existing_entry := await self.async_set_unique_id(to_import[CONF_HOST]):
            if existing_entry.options != to_import:
                await self.hass.config_entries.async_remove(existing_entry.entry_id)

        return self.async_create_entry(data=to_import)
