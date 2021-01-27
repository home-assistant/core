"""Config flow for Rako."""
import asyncio
from typing import Any, Dict, Optional

from python_rako import Bridge, discover_bridge
from python_rako.const import RAKO_BRIDGE_DEFAULT_PORT
from python_rako.exceptions import RakoBridgeError
from python_rako.model import BridgeInfo
import voluptuous as vol

from homeassistant.components.rako.const import CONF_MAC_ADDRESS, DOMAIN
from homeassistant.config_entries import CONN_CLASS_LOCAL_PUSH, ConfigFlow
from homeassistant.const import CONF_BASE, CONF_HOST, CONF_PORT
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType


class RakoConfigFlow(ConfigFlow, domain=DOMAIN):
    """RakoConfigFlow."""

    VERSION = 1
    CONNECTION_CLASS = CONN_CLASS_LOCAL_PUSH

    async def async_step_user(
        self, user_input: Optional[ConfigType] = None
    ) -> Dict[str, Any]:
        """Handle a flow initiated by the user."""
        if user_input is None:
            host = None
            try:
                host = await asyncio.wait_for(discover_bridge(), timeout=5.0)
            except asyncio.TimeoutError:
                pass

            if host:
                return self._show_setup_form(host)
            return self._show_setup_form(errors={CONF_BASE: "no_devices_found"})

        try:
            bridge_info = await self._get_bridge_info(
                user_input[CONF_HOST], user_input[CONF_PORT]
            )
        except (RakoBridgeError, asyncio.TimeoutError):
            return self._show_setup_form(errors={CONF_BASE: "cannot_connect"})

        await self.async_set_unique_id(
            unique_id=bridge_info.hostMAC, raise_on_progress=True
        )
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=f"Rako Bridge: {bridge_info.hostMAC}",
            data={
                CONF_HOST: user_input[CONF_HOST],
                CONF_PORT: user_input[CONF_PORT],
                CONF_MAC_ADDRESS: bridge_info.hostMAC,
            },
        )

    def _show_setup_form(
        self, host: Optional[str] = None, errors: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Show the setup form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=host): str,
                    vol.Required(CONF_PORT, default=RAKO_BRIDGE_DEFAULT_PORT): int,
                }
            ),
            errors=errors or {},
        )

    async def _get_bridge_info(self, host, port) -> BridgeInfo:
        session = async_get_clientsession(self.hass)
        bridge = Bridge(host, port)
        return await asyncio.wait_for(bridge.get_info(session), timeout=5.0)
