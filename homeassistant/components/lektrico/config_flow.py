"""Config flow for Lektrico Charging Station."""
from __future__ import annotations

from typing import Any

from lektricowifi import lektricowifi
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_FRIENDLY_NAME, CONF_HOST
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN


class LektricoFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a Lektrico config flow."""

    VERSION = 1

    host: str
    friendly_name: str
    serial_number: str

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initiated by the user."""
        print("Handle a flow initiated by the user")
        if user_input is None:
            return self._async_show_setup_form()

        self.host = user_input[CONF_HOST]
        self.friendly_name = user_input[CONF_FRIENDLY_NAME]

        return self._async_create_entry()

    @callback
    def _async_show_setup_form(
        self, errors: dict[str, str] | None = None
    ) -> FlowResult:
        """Show the setup form to the user."""
        print("Show the setup form to the user.")
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_FRIENDLY_NAME): str,
                    vol.Required(CONF_HOST): str,
                }
            ),
            errors=errors or {},
        )

    @callback
    def _async_create_entry(self) -> FlowResult:
        return self.async_create_entry(
            title=self.friendly_name,
            data={CONF_HOST: self.host, CONF_FRIENDLY_NAME: self.friendly_name},
        )

    async def _get_lektrico_serial_number(self, raise_on_progress: bool = True) -> None:
        """Get device information from a Lektrico device."""
        session = async_get_clientsession(self.hass)
        charger = lektricowifi.Charger(
            host=self.host,
            session=session,
        )
        await charger.charger_info()
        # self.serial_number = "Lektrico"
