"""Implementation of a QS Cloud Interface and related config entries."""
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant import config_entries, data_entry_flow
from homeassistant.const import (
    CONF_NAME, CONF_LATITUDE, CONF_LONGITUDE, CONF_ICON, CONF_RADIUS)
from homeassistant.core import callback
from homeassistant.util import slugify

from .qs import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry):
    """Set up config entry."""
    entry = config_entry.data
    name = entry[CONF_NAME]
    zone = Zone(hass, name, entry[CONF_LATITUDE], entry[CONF_LONGITUDE],
                entry.get(CONF_RADIUS, DEFAULT_RADIUS), entry.get(CONF_ICON),
                entry.get(CONF_PASSIVE, DEFAULT_PASSIVE))
    zone.entity_id = async_generate_entity_id(
        ENTITY_ID_FORMAT, name, None, hass)
    hass.async_add_job(zone.async_update_ha_state())
    hass.data[DOMAIN][slugify(name)] = zone
    return True


async def async_unload_entry(hass, config_entry):
    """Unload a config entry."""
    zones = hass.data[DOMAIN]
    name = slugify(config_entry.data[CONF_NAME])
    zone = zones.pop(name)
    await zone.async_remove()
    return True



@config_entries.HANDLERS.register(DOMAIN)
class QSCloudFlowHandler(data_entry_flow.FlowHandler):
    """Qwikswitch config flow."""

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
