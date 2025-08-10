"""Config flow to configure Dynalite hub."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers import config_validation as cv

from .bridge import DynaliteBridge
from .const import DEFAULT_PORT, DOMAIN, LOGGER
from .convert_config import convert_config


class DynaliteFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a Dynalite config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the Dynalite flow."""
        self.host = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
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

    async def _try_create(self, info: dict[str, Any]) -> ConfigFlowResult:
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
