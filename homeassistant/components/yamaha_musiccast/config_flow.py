"""Config flow for MusicCast."""
# import my_pypi_dependency

from typing import Any, Dict, Optional

from pyamaha import AsyncDevice, System
from requests.exceptions import ConnectionError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import (
    CONN_CLASS_LOCAL_POLL,
    SOURCE_ZEROCONF,
    ConfigFlow,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from homeassistant.const import CONF_HOST, CONF_MAC, CONF_NAME
from homeassistant.helpers import config_entry_flow
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN


class MusicCastFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a MusicCast config flow."""

    VERSION = 1
    CONNECTION_CLASS = CONN_CLASS_LOCAL_POLL

    async def async_step_user(
        self, user_input: Optional[ConfigType] = None
    ) -> Dict[str, Any]:
        """Handle a flow initiated by the user."""
        return await self._handle_config_flow(user_input)

    async def _handle_config_flow(
        self, user_input: Optional[ConfigType] = None, prepare: bool = False
    ) -> Dict[str, Any]:
        """Config flow handler for MusicCast."""

        errors = {}

        # Request user input, unless we are preparing discovery flow
        if user_input is None and not prepare:
            # if source == SOURCE_ZEROCONF:
            #    return self._show_confirm_dialog()
            return self._show_setup_form()

        title = user_input[CONF_HOST]

        # Check if device is a MusicCast device
        device = AsyncDevice(async_get_clientsession(self.hass), user_input[CONF_HOST])

        try:
            device.request(System.get_device_info())
        except ConnectionError:
            errors["base"] = "cannot_connect"

        if not errors:
            return self.async_create_entry(
                title=title,
                data={CONF_HOST: user_input[CONF_HOST]},
            )

        return self._show_setup_form(errors)

    def _show_setup_form(self, errors: Optional[Dict] = None) -> Dict[str, Any]:
        """Show the setup form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_HOST): str}),
            errors=errors or {},
        )


# config_entry_flow.register_discovery_flow(
#     DOMAIN, "MusicCast", _async_has_devices, config_entries.CONN_CLASS_UNKNOWN
# )
