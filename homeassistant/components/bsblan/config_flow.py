"""Config flow for BSB-Lan integration."""
from __future__ import annotations

import logging

from bsblan import BSBLan, BSBLanError, Info
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .const import CONF_DEVICE_IDENT, CONF_PASSKEY, DOMAIN

_LOGGER = logging.getLogger(__name__)


class BSBLanFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a BSBLan config flow."""

    VERSION = 1

    async def async_step_user(self, user_input: ConfigType | None = None) -> FlowResult:
        """Handle a flow initiated by the user."""
        if user_input is None:
            return self._show_setup_form()

        try:
            info = await self._get_bsblan_info(
                host=user_input[CONF_HOST],
                port=user_input[CONF_PORT],
                passkey=user_input.get(CONF_PASSKEY),
                username=user_input.get(CONF_USERNAME),
                password=user_input.get(CONF_PASSWORD),
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
                CONF_USERNAME: user_input.get(CONF_USERNAME),
                CONF_PASSWORD: user_input.get(CONF_PASSWORD),
            },
        )

    def _show_setup_form(self, errors: dict | None = None) -> FlowResult:
        """Show the setup form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Optional(CONF_PORT, default=80): int,
                    vol.Optional(CONF_PASSKEY): str,
                    vol.Optional(CONF_USERNAME): str,
                    vol.Optional(CONF_PASSWORD): str,
                }
            ),
            errors=errors or {},
        )

    async def _get_bsblan_info(
        self,
        host: str,
        username: str | None,
        password: str | None,
        passkey: str | None,
        port: int,
    ) -> Info:
        """Get device information from an BSBLan device."""
        session = async_get_clientsession(self.hass)
        _LOGGER.debug("request bsblan.info:")
        bsblan = BSBLan(
            host,
            username=username,
            password=password,
            passkey=passkey,
            port=port,
            session=session,
        )
        return await bsblan.info()
