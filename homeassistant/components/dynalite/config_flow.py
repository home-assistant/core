"""Config flow to configure Dynalite hub."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue

from .bridge import DynaliteBridge
from .const import DEFAULT_PORT, DOMAIN, LOGGER
from .convert_config import convert_config


class DynaliteFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Dynalite config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the Dynalite flow."""
        self.host = None

    async def async_step_import(self, import_info: dict[str, Any]) -> FlowResult:
        """Import a new bridge as a config entry."""
        LOGGER.debug("Starting async_step_import (deprecated) - %s", import_info)
        # Raise an issue that this is deprecated and has been imported
        async_create_issue(
            self.hass,
            HOMEASSISTANT_DOMAIN,
            f"deprecated_yaml_{DOMAIN}",
            is_fixable=False,
            is_persistent=False,
            issue_domain=DOMAIN,
            severity=IssueSeverity.WARNING,
            translation_key="deprecated_yaml",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": "Dynalite",
            },
        )

        host = import_info[CONF_HOST]
        # Check if host already exists
        for entry in self._async_current_entries():
            if entry.data[CONF_HOST] == host:
                self.hass.config_entries.async_update_entry(
                    entry, data=dict(import_info)
                )
                return self.async_abort(reason="already_configured")

        # New entry
        return await self._try_create(import_info)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step when user initializes a integration."""
        if user_input is not None:
            return await self._try_create(user_input)

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST): cv.string,
                vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema)

    async def _try_create(self, info: dict[str, Any]) -> FlowResult:
        """Try to connect and if successful, create entry."""
        host = info[CONF_HOST]
        configured_hosts = [
            entry.data[CONF_HOST] for entry in self._async_current_entries()
        ]
        if host in configured_hosts:
            return self.async_abort(reason="already_configured")
        bridge = DynaliteBridge(self.hass, convert_config(info))
        if not await bridge.async_setup():
            LOGGER.error("Unable to setup bridge - import info=%s", info)
            return self.async_abort(reason="cannot_connect")
        LOGGER.debug("Creating entry for the bridge - %s", info)
        return self.async_create_entry(title=info[CONF_HOST], data=info)
