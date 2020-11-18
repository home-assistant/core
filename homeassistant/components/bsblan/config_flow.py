"""Config flow for BSB-Lan integration."""
import logging
from typing import Any, Dict, Optional

from bsblan import BSBLan, BSBLanError, Info
import voluptuous as vol

from homeassistant.config_entries import CONN_CLASS_LOCAL_POLL, ConfigFlow
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .const import (  # pylint:disable=unused-import
    CONF_DEVICE_IDENT,
    CONF_PASSKEY,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class BSBLanFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a BSBLan config flow."""

    VERSION = 1
    CONNECTION_CLASS = CONN_CLASS_LOCAL_POLL

    async def async_step_user(
        self, user_input: Optional[ConfigType] = None
    ) -> Dict[str, Any]:
        """Handle a flow initiated by the user."""
        if user_input is None:
            return self._show_setup_form()

        try:
            info = await self._get_bsblan_info(
                host=user_input[CONF_HOST],
                port=user_input[CONF_PORT],
                passkey=user_input.get(CONF_PASSKEY),
            )
        except BSBLanError:
            return self._show_setup_form({"base": "cannot_connect"})

        # Check if already configured
        await self.async_set_unique_id(info.device_identification)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=info.device_identification,
            data={
                CONF_HOST: user_input[CONF_HOST],
                CONF_PORT: user_input[CONF_PORT],
                CONF_PASSKEY: user_input.get(CONF_PASSKEY),
                CONF_DEVICE_IDENT: info.device_identification,
            },
        )

    def _show_setup_form(self, errors: Optional[Dict] = None) -> Dict[str, Any]:
        """Show the setup form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Optional(CONF_PORT, default=80): int,
                    vol.Optional(CONF_PASSKEY): str,
                }
            ),
            errors=errors or {},
        )

    async def _get_bsblan_info(
        self, host: str, passkey: Optional[str], port: int
    ) -> Info:
        """Get device information from an BSBLan device."""
        session = async_get_clientsession(self.hass)
        _LOGGER.debug("request bsblan.info:")
        bsblan = BSBLan(
            host, passkey=passkey, port=port, session=session, loop=self.hass.loop
        )
        return await bsblan.info()
