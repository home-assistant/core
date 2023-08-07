"""Config flow for Ping (ICMP) integration."""
from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any, cast

import voluptuous as vol

from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN
from homeassistant.data_entry_flow import FlowResult, FlowResultType
from homeassistant.helpers import selector
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaConfigFlowHandler,
    SchemaFlowFormStep,
)

from .const import CONF_PING_COUNT, DEFAULT_PING_COUNT, DOMAIN

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

        self._async_abort_entries_match({CONF_HOST: import_info[CONF_HOST]})
        flow_result = self.async_create_entry(data=import_info)

        # when config entry successfully imported create a deprecated yaml issue
        if flow_result["type"] == FlowResultType.CREATE_ENTRY:
            async_create_issue(
                self.hass,
                HOMEASSISTANT_DOMAIN,
                f"deprecated_yaml_{DOMAIN}",
                breaks_in_ha_version="2024.2.0",
                is_fixable=False,
                issue_domain=DOMAIN,
                severity=IssueSeverity.WARNING,
                translation_key="deprecated_yaml",
                translation_placeholders={
                    "domain": DOMAIN,
                    "integration_title": "Ping",
                },
            )

        return flow_result
