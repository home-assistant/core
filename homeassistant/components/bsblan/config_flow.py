"""Config flow for BSB-Lan integration."""
from __future__ import annotations

from typing import Any

from bsblan import BSBLAN, BSBLANError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import format_mac

from .const import CONF_PASSKEY, DEFAULT_PORT, DOMAIN


class BSBLANFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a BSBLAN config flow."""

    VERSION = 1

    host: str
    port: int
    mac: str
    passkey: str | None = None
    username: str | None = None
    password: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initiated by the user."""
        if user_input is None:
            return self._show_setup_form()

        self.host = user_input[CONF_HOST]
        self.port = user_input[CONF_PORT]
        self.passkey = user_input.get(CONF_PASSKEY)
        self.username = user_input.get(CONF_USERNAME)
        self.password = user_input.get(CONF_PASSWORD)

        try:
            await self._get_bsblan_info()
        except BSBLANError:
            return self._show_setup_form({"base": "cannot_connect"})

        return self._async_create_entry()

    @callback
    def _show_setup_form(self, errors: dict | None = None) -> FlowResult:
        """Show the setup form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
                    vol.Optional(CONF_PASSKEY): str,
                    vol.Optional(CONF_USERNAME): str,
                    vol.Optional(CONF_PASSWORD): str,
                }
            ),
            errors=errors or {},
        )

    @callback
    def _async_create_entry(self) -> FlowResult:
        return self.async_create_entry(
            title=format_mac(self.mac),
            data={
                CONF_HOST: self.host,
                CONF_PORT: self.port,
                CONF_PASSKEY: self.passkey,
                CONF_USERNAME: self.username,
                CONF_PASSWORD: self.password,
            },
        )

    async def _get_bsblan_info(self, raise_on_progress: bool = True) -> None:
        """Get device information from an BSBLAN device."""
        session = async_get_clientsession(self.hass)
        bsblan = BSBLAN(
            host=self.host,
            username=self.username,
            password=self.password,
            passkey=self.passkey,
            port=self.port,
            session=session,
        )
        device = await bsblan.device()
        self.mac = device.MAC

        await self.async_set_unique_id(
            format_mac(self.mac), raise_on_progress=raise_on_progress
        )
        self._abort_if_unique_id_configured(
            updates={
                CONF_HOST: self.host,
                CONF_PORT: self.port,
            }
        )
