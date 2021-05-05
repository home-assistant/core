"""Config flow for Rako."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from python_rako import BridgeDescription, discover_bridge
from python_rako.bridge import Bridge
from python_rako.const import RAKO_BRIDGE_DEFAULT_PORT
from python_rako.exceptions import RakoBridgeError
from python_rako.model import BridgeInfo
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_BASE, CONF_HOST, CONF_MAC, CONF_NAME, CONF_PORT
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class RakoConfigFlow(ConfigFlow, domain=DOMAIN):
    """RakoConfigFlow."""

    VERSION = 1
    rako_timeout = 3.0

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initiated by the user."""
        bridge_desc: BridgeDescription = {}
        if user_input is None:
            try:
                bridge_desc = await asyncio.wait_for(
                    discover_bridge(), timeout=self.rako_timeout
                )
            except (asyncio.TimeoutError, ValueError) as ex:
                _LOGGER.warning("Couldn't auto discover Rako bridge %s", ex)

            if bridge_desc:
                return self._show_setup_form(bridge_desc=bridge_desc)
            return self._show_setup_form(
                bridge_desc=bridge_desc, errors={CONF_BASE: "no_devices_found"}
            )

        bridge_desc = {
            "host": user_input[CONF_HOST],
            "port": user_input[CONF_PORT],
            "mac": user_input[CONF_MAC],
            "name": user_input[CONF_NAME]
            if user_input.get(CONF_NAME)
            else user_input[CONF_MAC],
        }
        try:
            # just check we can connect using the given data
            await self._get_bridge_info(bridge_desc)
        except (RakoBridgeError, asyncio.TimeoutError):
            return self._show_setup_form(
                bridge_desc=bridge_desc, errors={CONF_BASE: "cannot_connect"}
            )

        await self.async_set_unique_id(
            unique_id=user_input[CONF_MAC], raise_on_progress=True
        )
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=f"Rako Bridge ({bridge_desc['name']})",
            data=bridge_desc,
        )

    def _show_setup_form(
        self,
        bridge_desc: BridgeDescription,
        errors: dict[str, str] | None = None,
    ) -> FlowResult:
        """Show the setup form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=bridge_desc.get("host")): str,
                    vol.Required(CONF_PORT, default=RAKO_BRIDGE_DEFAULT_PORT): int,
                    vol.Optional(CONF_NAME, default=bridge_desc.get("name")): str,
                    vol.Required(CONF_MAC, default=bridge_desc.get("mac")): str,
                }
            ),
            errors=errors or {},
        )

    async def _get_bridge_info(self, bridge_desc: BridgeDescription) -> BridgeInfo:
        session = async_get_clientsession(self.hass)
        bridge = Bridge(**bridge_desc)
        return await asyncio.wait_for(
            bridge.get_info(session), timeout=self.rako_timeout
        )
