"""Config flow for Lektrico Charging Station."""
# import my_pypi_dependency

# from homeassistant.core import HomeAssistant
# from homeassistant.helpers import config_entry_flow

# from .const import DOMAIN


# async def _async_has_devices(hass: HomeAssistant) -> bool:
#     """Return if there are devices that can be discovered."""
#     # Check if there are any devices that can be discovered in the network.
#     devices = await hass.async_add_executor_job(my_pypi_dependency.discover)
#     return len(devices) > 0


# config_entry_flow.register_discovery_flow(DOMAIN, "Lektrico Charging Station", _async_has_devices)


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

        # try:
        #     await self._get_lektrico_serial_number(raise_on_progress=False)
        # except ElgatoError:
        #     return self._async_show_setup_form({"base": "cannot_connect"})

        return self._async_create_entry()

    async def async_step_zeroconf(self, discovery_info: dict[str, Any]) -> FlowResult:
        """Handle zeroconf discovery."""
        self.host = discovery_info[CONF_HOST]

        # try:
        #     await self._get_lektrico_serial_number()
        # except ElgatoError:
        #     return self.async_abort(reason="cannot_connect")

        self._set_confirm_only()
        return self.async_show_form(
            step_id="zeroconf_confirm",
            # description_placeholders={"serial_number": self.serial_number},
        )

    async def async_step_zeroconf_confirm(
        self, _: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initiated by zeroconf."""
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
            # title="Lektrico",
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
