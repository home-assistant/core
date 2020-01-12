"""Config flow to configure the SimpliSafe component."""
from collections import OrderedDict

from simplipy import API
from simplipy.errors import SimplipyError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_CODE,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_TOKEN,
    CONF_USERNAME,
)
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN


@callback
def configured_instances(hass):
    """Return a set of configured SimpliSafe instances."""
    return set(
        entry.data[CONF_USERNAME] for entry in hass.config_entries.async_entries(DOMAIN)
    )


@config_entries.HANDLERS.register(DOMAIN)
class SimpliSafeFlowHandler(config_entries.ConfigFlow):
    """Handle a SimpliSafe config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize the config flow."""
        self.data_schema = OrderedDict()
        self.data_schema[vol.Required(CONF_USERNAME)] = str
        self.data_schema[vol.Required(CONF_PASSWORD)] = str
        self.data_schema[vol.Optional(CONF_CODE)] = str

    async def _show_form(self, errors=None):
        """Show the form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(self.data_schema),
            errors=errors if errors else {},
        )

    async def async_step_import(self, import_config):
        """Import a config entry from configuration.yaml."""
        return await self.async_step_user(import_config)

    async def async_step_user(self, user_input=None):
        """Handle the start of the config flow."""

        if not user_input:
            return await self._show_form()

        if user_input[CONF_USERNAME] in configured_instances(self.hass):
            return await self._show_form({CONF_USERNAME: "identifier_exists"})

        username = user_input[CONF_USERNAME]
        websession = aiohttp_client.async_get_clientsession(self.hass)

        try:
            simplisafe = await API.login_via_credentials(
                username, user_input[CONF_PASSWORD], websession
            )
        except SimplipyError:
            return await self._show_form({"base": "invalid_credentials"})

        scan_interval = user_input.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

        return self.async_create_entry(
            title=user_input[CONF_USERNAME],
            data={
                CONF_USERNAME: username,
                CONF_TOKEN: simplisafe.refresh_token,
                CONF_SCAN_INTERVAL: scan_interval.seconds,
            },
        )
