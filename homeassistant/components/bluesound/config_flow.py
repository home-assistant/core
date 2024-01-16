"""Config flow to configure the BlueSound integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components import zeroconf
from homeassistant.config_entries import ConfigFlow
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    CONF_UUID,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN, DEFAULT_PORT

_LOGGER = logging.getLogger(__name__)


class BlueSoundFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle an BlueSound config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Set up the instance."""
        self.discovery_info: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initiated by the user."""
        if user_input is None:
            return self._show_setup_form()

        unique_id = user_input[CONF_UUID]

        if not unique_id:
            _LOGGER.debug("Unable to determine unique id")

        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured(updates={CONF_HOST: user_input[CONF_HOST]})

        return self.async_create_entry(title=user_input[CONF_HOST], data=user_input)

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> FlowResult:
        """Handle zeroconf discovery."""
        host = discovery_info.host

        _LOGGER.debug("Bluesound zerconf discovery got host %s", host)

        # Avoid probing devices that already have an entry
        self._async_abort_entries_match({CONF_HOST: host})

        port = discovery_info.port
        zctype = discovery_info.type
        name = discovery_info.name.replace(f".{zctype}", "")

        unique_id = f"{host}:{port}"

        await self.async_set_unique_id(unique_id)

        _LOGGER.debug("Bluesound starting zerconf setup for %s at %s:%d", name, host, port)

        self.discovery_info.update(
            {
                CONF_HOST: host,
                CONF_PORT: port,
                CONF_NAME: name,
            }
        )

        self.context.update({"title_placeholders": {"name": name}})

        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a confirmation flow initiated by zeroconf."""
        if user_input is None:
            return self.async_show_form(
                step_id="zeroconf_confirm",
                description_placeholders={"name": self.discovery_info[CONF_NAME]},
                errors={},
            )

        return self.async_create_entry(
            title=self.discovery_info[CONF_NAME],
            data=self.discovery_info,
        )

    def _show_setup_form(self, errors: dict | None = None) -> FlowResult:
        """Show the setup form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Optional(CONF_NAME): str,
                    vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
                }
            ),
            errors=errors or {},
        )
