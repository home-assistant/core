"""Config flow to configure the AIS Drive Service component."""

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_API_KEY, CONF_ELEVATION, CONF_LATITUDE, CONF_LONGITUDE)
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client, config_validation as cv

from .const import DOMAIN


def setUrl(url):
    global G_AUTH_URL
    G_AUTH_URL = url

@callback
def configured_drivers(hass):
    """Return a set of configured Drives instances."""
    return set(
        '{0}, {1}'.format(
            entry.data.get(CONF_LATITUDE, hass.config.latitude),
            entry.data.get(CONF_LONGITUDE, hass.config.longitude))
        for entry in hass.config_entries.async_entries(DOMAIN))


@config_entries.HANDLERS.register(DOMAIN)
class DriveFlowHandler(config_entries.ConfigFlow):
    """Drive config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize zone configuration flow."""
        pass

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        return await self.async_step_confirm(user_input)

    async def async_step_confirm(self, user_input=None):
        """Handle a flow start."""
        errors = {}
        if user_input is not None:
            return await self.async_step_drive_name(user_input=None)
        return self.async_show_form(
            step_id='confirm',
            errors=errors,
        )

    async def async_step_drive_name(self, user_input=None):
        """Handle a flow start."""
        errors = {}
        data_schema = vol.Schema({
            vol.Required('service'): vol.In(list(["Amazon Drive", "Dropbox", "Google Drive",
                                                  "Mega", "Microsoft OneDrive", "Yandex Disk"])),
            vol.Required('name'): str,
        })
        if user_input is not None:
            # rclone config create mydrive drive config_is_local false
            return await self.async_step_token(user_input=None)

        return self.async_show_form(
            step_id='drive_name',
            errors=errors,
            data_schema=data_schema,
        )

    async def async_step_token(self, user_input=None):
        """Handle a flow start."""
        errors = {}
        data_schema = vol.Schema({
            vol.Required('token_key'): str,
        })
        if user_input is not None:
            return self.async_create_entry(
                title="Dysk",
                data=user_input,
            )

        return self.async_show_form(
            step_id='token',
            errors=errors,
            description_placeholders={
                'auth_url': "https://www.ai-speaker.com",
            },
            data_schema=data_schema,
        )


