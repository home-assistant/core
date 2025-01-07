"""Config flow to configure the Elgato Light integration."""

from __future__ import annotations

from typing import Any

from elgato import Elgato, ElgatoError
import voluptuous as vol

from homeassistant.components import onboarding, zeroconf
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_MAC
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN


class ElgatoFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a Elgato Light config flow."""

    VERSION = 1

    host: str
    port: int
    serial_number: str
    mac: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        if user_input is None:
            return self._async_show_setup_form()

        self.host = user_input[CONF_HOST]

        try:
            await self._get_elgato_serial_number(raise_on_progress=False)
        except ElgatoError:
            return self._async_show_setup_form({"base": "cannot_connect"})

        return self._async_create_entry()

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        self.host = discovery_info.host
        self.mac = discovery_info.properties.get("id")

        try:
            await self._get_elgato_serial_number()
        except ElgatoError:
            return self.async_abort(reason="cannot_connect")

        if not onboarding.async_is_onboarded(self.hass):
            return self._async_create_entry()

        self._set_confirm_only()
        return self.async_show_form(
            step_id="zeroconf_confirm",
            description_placeholders={"serial_number": self.serial_number},
        )

    async def async_step_zeroconf_confirm(
        self, _: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by zeroconf."""
        return self._async_create_entry()

    @callback
    def _async_show_setup_form(
        self, errors: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Show the setup form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                }
            ),
            errors=errors or {},
        )

    @callback
    def _async_create_entry(self) -> ConfigFlowResult:
        return self.async_create_entry(
            title=self.serial_number,
            data={
                CONF_HOST: self.host,
                CONF_MAC: self.mac,
            },
        )

    async def _get_elgato_serial_number(self, raise_on_progress: bool = True) -> None:
        """Get device information from an Elgato Light device."""
        session = async_get_clientsession(self.hass)
        elgato = Elgato(
            host=self.host,
            session=session,
        )
        info = await elgato.info()

        # Check if already configured
        await self.async_set_unique_id(
            info.serial_number, raise_on_progress=raise_on_progress
        )
        self._abort_if_unique_id_configured(
            updates={CONF_HOST: self.host, CONF_MAC: self.mac}
        )

        self.serial_number = info.serial_number
