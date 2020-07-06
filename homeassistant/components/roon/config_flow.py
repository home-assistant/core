"""Config flow for Roon."""
import logging
import voluptuous as vol
from asyncio import sleep
from homeassistant.core import callback
from homeassistant import config_entries
import homeassistant.helpers.config_validation as cv
from collections import OrderedDict
from homeassistant.const import CONF_HOST, CONF_API_KEY
from .const import DOMAIN, CONF_CUSTOM_PLAY_ACTION, ROON_APPINFO, CONFIG_SCHEMA

_LOGGER = logging.getLogger(__name__)

@callback
def configured_hosts(hass):
    """Return a set of the configured hosts."""
    return set(entry.data[CONF_HOST] for entry
               in hass.config_entries.async_entries(DOMAIN))


@config_entries.HANDLERS.register(DOMAIN)
class FlowHandler(config_entries.ConfigFlow):
    """Handle a config flow."""
    user_input = {}

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        return await self.async_step_init()

    async def async_step_init(self, user_input=None):
        """Confirm the setup."""
        errors = {}

        if user_input is not None:
            return await self.async_step_link(user_input)

        # TODO: auto discovery of Roon server

        fields = OrderedDict()
        fields[vol.Required(CONF_HOST)] = str
        fields[vol.Optional(CONF_CUSTOM_PLAY_ACTION)] = str

        return self.async_show_form(
            step_id='init',
            data_schema=vol.Schema(fields)
            )

    async def async_step_link(self, user_input=None):
        """Attempt to link with the Roon core.
        Given a configured host, will ask the user to approve the extension in roon.
        """
        errors = {}

        if user_input and user_input.get(CONF_API_KEY):
            return self.async_create_entry(
                    title=user_input[CONF_HOST], data=user_input)

        if user_input:
            self.user_input = user_input

        if not user_input and self.user_input:
            token = None
            try:
                from roon import RoonApi
                count = 0
                roonapi = RoonApi(ROON_APPINFO, token, self.user_input[CONF_HOST], blocking_init=False)
                while count < 30:
                    # wait a maximum of 30 seconds for the token
                    token = roonapi.token
                    count += 1
                    if token:
                        break
                    else:
                        await sleep(1, self.hass.loop)
            except Exception:
                errors['base'] = 'cannot_connect'
            if not token:
                errors['base'] = 'register_failed'
            else:
                user_input = self.user_input
                user_input[CONF_API_KEY] = token
                return await self.async_step_link(user_input)

        return self.async_show_form(
            step_id='link',
            errors=errors,
        )

    async def async_step_import(self, user_input):
        """Import a config entry.

        Special type of import, we're not actually going to store any data.
        Instead, we're going to rely on the values that are in config file.
        """
        return await self.async_step_user(user_input)
