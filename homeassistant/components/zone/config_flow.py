"""Config flow to configure zone component."""

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant import config_entries
from homeassistant.const import (
    CONF_NAME, CONF_LATITUDE, CONF_LONGITUDE, CONF_ICON, CONF_RADIUS)
from homeassistant.core import callback
from homeassistant.util import slugify

from .const import CONF_PASSIVE, DOMAIN, HOME_ZONE


@callback
def configured_zones(hass):
    """Return a set of the configured zones."""
    return set((slugify(entry.data[CONF_NAME])) for
               entry in hass.config_entries.async_entries(DOMAIN))


@config_entries.HANDLERS.register(DOMAIN)
class ZoneFlowHandler(config_entries.ConfigFlow):
    """Zone config flow."""

    VERSION = 1

    def __init__(self):
        """Initialize zone configuration flow."""
        pass

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        return await self.async_step_init(user_input)

    async def async_step_init(self, user_input=None):
        """Handle a flow start."""
        errors = {}

        if user_input is not None:
            name = slugify(user_input[CONF_NAME])
            if name not in configured_zones(self.hass) and name != HOME_ZONE:
                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data=user_input,
                )
            errors['base'] = 'name_exists'

        return self.async_show_form(
            step_id='init',
            data_schema=vol.Schema({
                vol.Required(CONF_NAME): str,
                vol.Required(CONF_LATITUDE): cv.latitude,
                vol.Required(CONF_LONGITUDE): cv.longitude,
                vol.Optional(CONF_RADIUS): vol.Coerce(float),
                vol.Optional(CONF_ICON): str,
                vol.Optional(CONF_PASSIVE): bool,
            }),
            errors=errors,
        )
