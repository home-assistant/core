"""Config flow to configure the AIS Drive Service component."""

import voluptuous as vol
import logging
import asyncio
from homeassistant import config_entries
from homeassistant.const import (CONF_NAME, CONF_TYPE)
from homeassistant.core import callback
from homeassistant.util import slugify
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
DRIVE_NAME = None
DRIVE_TYPE = None

@callback
def configured_drivers(hass):
    """Return a set of configured Drives instances."""
    return set(entry.data.get(CONF_NAME)
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
        global DRIVE_NAME, DRIVE_TYPE
        errors = {}
        from homeassistant.components.ais_drives_service import DRIVES_TYPES
        names = []
        for obj in DRIVES_TYPES.values():
            names.append(obj[0])
        data_schema = vol.Schema({
            vol.Required(CONF_TYPE): vol.In(list(names)),
            vol.Required(CONF_NAME): str,
        })
        if user_input is not None:
            DRIVE_NAME = user_input.get(CONF_NAME)
            DRIVE_TYPE = user_input.get(CONF_TYPE)
            if slugify(DRIVE_NAME) in configured_drivers(self.hass):
                errors = {CONF_NAME: 'identifier_exists'}

            if errors == {}:
                # get url from rclone
                from homeassistant.components.ais_drives_service import rclone_get_auth_url
                d_type = ""
                for k, item in DRIVES_TYPES.items():
                    if item[0] == DRIVE_TYPE:
                        d_type = k
                url = rclone_get_auth_url(DRIVE_NAME, d_type)
                #
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
        if user_input is not None and 'token_key' in user_input:
            # remove if exists
            exists_entries = [entry.entry_id for entry in self._async_current_entries()]
            if exists_entries:
                await asyncio.wait([self.hass.config_entries.async_remove(entry_id)
                                    for entry_id in exists_entries])

            # add new one
            user_input[CONF_NAME] = DRIVE_NAME
            user_input[CONF_TYPE] = DRIVE_TYPE

            return self.async_create_entry(
                title="Zdalne dyski",
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
