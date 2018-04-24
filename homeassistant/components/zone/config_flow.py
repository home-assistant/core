"""Config flow to configure zone component."""

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant import config_entries, data_entry_flow
from homeassistant.const import (
    CONF_NAME, CONF_LATITUDE, CONF_LONGITUDE, CONF_ICON, CONF_RADIUS)
from homeassistant.core import callback
from homeassistant.util import slugify

from .const import CONF_PASSIVE, DOMAIN


@callback
def configured_zones(hass):
    """Return a set of the configured hosts."""
    return set((slugify(entry.data[CONF_NAME])) for
               entry in hass.config_entries.async_entries(DOMAIN))


@config_entries.HANDLERS.register(DOMAIN)
class ZoneFlowHandler(data_entry_flow.FlowHandler):
    """Zone config flow."""

    VERSION = 1

    def __init__(self):
        """Initialize zone configuration flow."""
        pass

    async def async_step_init(self, user_input=None):
        """Handle a flow start."""
        errors = {}

        if user_input is not None:
            if slugify(user_input[CONF_NAME]) not in configured_zones(self.hass):
                return self.async_create_entry(
                    title='Zone ' + user_input[CONF_NAME],
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

    async def async_step_import(self, import_config):
        """Import a configured zone as a config entry.

        This flow is triggered by `async_setup` for configured zones.

        This will execute for any zone that does not have a
        config entry yet (based on latitude and longitude).
        """
        return self.async_create_entry(
            title='Zone ' + import_config[CONF_NAME],
            data=import_config,
        )
