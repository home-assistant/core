"""Config flow to configure emulated_roku component."""

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.util import slugify
from .const import (DOMAIN, CONF_LISTEN_PORT, CONF_HOST_IP,
                    CONF_ADVERTISE_IP, CONF_ADVERTISE_PORT,
                    CONF_UPNP_BIND_MULTICAST,
                    DEFAULT_UPNP_BIND_MULTICAST)


@callback
def configured_servers(hass):
    """Return a set of the configured servers."""
    return set(slugify(entry.data[CONF_NAME]) for entry
               in hass.config_entries.async_entries(DOMAIN))


@config_entries.HANDLERS.register(DOMAIN)
class EmulatedRokuFlowHandler(config_entries.ConfigFlow):
    """Handle an emulated_roku config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    _hassio_discovery = None

    def __init__(self):
        """Initialize emulated_roku configuration flow."""
        pass

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is not None:
            name = slugify(user_input[CONF_NAME])

            if name in configured_servers(self.hass):
                return self.async_abort(reason='name_exists')

            return self.async_create_entry(
                title=user_input[CONF_NAME],
                data=user_input
            )

        return self.async_show_form(
            step_id='user',
            data_schema=vol.Schema({
                vol.Required(CONF_NAME): str,
                vol.Required(CONF_LISTEN_PORT): vol.Coerce(int),
                vol.Optional(CONF_HOST_IP): str,
                vol.Optional(CONF_ADVERTISE_IP): str,
                vol.Optional(CONF_ADVERTISE_PORT): vol.Coerce(int),
                vol.Optional(CONF_UPNP_BIND_MULTICAST,
                             default=DEFAULT_UPNP_BIND_MULTICAST): bool
            }),
            errors=errors
        )
