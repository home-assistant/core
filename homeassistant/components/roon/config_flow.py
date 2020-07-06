"""Config flow for Roon."""
from asyncio import sleep
from collections import OrderedDict
import logging

from roon import RoonApi
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY, CONF_HOST
from homeassistant.core import callback

from .const import CONF_CUSTOM_PLAY_ACTION, DOMAIN, ROON_APPINFO

_LOGGER = logging.getLogger(__name__)


@callback
def configured_hosts(hass):
    """Return a set of the configured hosts."""
    return {
        entry.data[CONF_HOST] for entry in hass.config_entries.async_entries(DOMAIN)
    }


@config_entries.HANDLERS.register(DOMAIN)
class FlowHandler(config_entries.ConfigFlow):
    """Handle a config flow."""

    user_input = {}
    roonapi = None

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        return await self.async_step_init()

    async def async_step_init(self, user_input=None):
        """Confirm the setup."""
        if user_input is not None:
            return await self.async_step_link(user_input)

        fields = OrderedDict()
        fields[vol.Required(CONF_HOST)] = str
        fields[vol.Optional(CONF_CUSTOM_PLAY_ACTION)] = str

        return self.async_show_form(step_id="init", data_schema=vol.Schema(fields))

    async def async_step_link(self, user_input=None):
        """Attempt to link with the Roon core.

        Given a configured host, will ask the user to approve the extension in roon.
        """
        errors = {}

        if user_input and user_input.get(CONF_API_KEY):
            return self.async_create_entry(title=user_input[CONF_HOST], data=user_input)

        if user_input:
            self.user_input = user_input

        if not user_input and self.user_input:
            token = None
            try:
                count = 0
                roonapi = RoonApi(
                    ROON_APPINFO, token, self.user_input[CONF_HOST], blocking_init=False
                )
                while count < 120:
                    # wait a maximum of 120 seconds for the token
                    token = roonapi.token
                    count += 1
                    if token:
                        break
                    await sleep(1, self.hass.loop)
            except Exception:  # pylint: disable=broad-except
                errors["base"] = "cannot_connect"
            if not token:
                errors["base"] = "register_failed"
            else:
                user_input = self.user_input
                user_input[CONF_API_KEY] = token
                return await self.async_step_link(user_input)

        return self.async_show_form(step_id="link", errors=errors,)

    async def async_step_import(self, user_input):
        """Import a config entry.

        Special type of import, we're not actually going to store any data.
        Instead, we're going to rely on the values that are in config file.
        """
        return await self.async_step_user(user_input)
