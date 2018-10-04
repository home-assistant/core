"""Config flow to configure Z-Wave."""
from collections import OrderedDict
import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback

from .const import (
    CONF_AUTOHEAL, CONF_POLLING_INTERVAL,
    CONF_USB_STICK_PATH, CONF_NETWORK_KEY,
    DEFAULT_CONF_AUTOHEAL, DEFAULT_CONF_USB_STICK_PATH,
    DEFAULT_POLLING_INTERVAL, DOMAIN)

_LOGGER = logging.getLogger(__name__)


@callback
def configured_hosts(hass):
    """Return a set of the configured hosts."""
    return set(entry.data[CONF_USB_STICK_PATH] for entry
               in hass.config_entries.async_entries(DOMAIN))


@config_entries.HANDLERS.register(DOMAIN)
class ZwaveFlowHandler(config_entries.ConfigFlow):
    """Handle a Z-Wave config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    def __init__(self):
        """Initialize the Z-Wave config flow."""
        self.usb_path = CONF_USB_STICK_PATH

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        return await self.async_step_init(user_input)

    async def async_step_init(self, user_input=None):
        """Handle a flow start."""
        if configured_hosts(self.hass):
            return self.async_abort(reason='one_instance_only')

        if user_input is not None:
            return self.async_create_entry(
                title="Z-Wave",
                data={
                    CONF_USB_STICK_PATH: user_input[CONF_USB_STICK_PATH],
                    CONF_NETWORK_KEY: user_input[CONF_NETWORK_KEY],
                    CONF_AUTOHEAL: user_input[CONF_AUTOHEAL],
                    CONF_POLLING_INTERVAL: user_input[CONF_POLLING_INTERVAL]
                },
            )

        fields = OrderedDict()
        fields[vol.Required(CONF_USB_STICK_PATH,
                            default=DEFAULT_CONF_USB_STICK_PATH)] = str
        fields[vol.Optional(CONF_NETWORK_KEY)] = str
        fields[vol.Optional(CONF_AUTOHEAL,
                            default=DEFAULT_CONF_AUTOHEAL)] = bool
        fields[vol.Optional(
            CONF_POLLING_INTERVAL,
            default=DEFAULT_POLLING_INTERVAL
        )] = vol.Coerce(int)

        return self.async_show_form(
            step_id='init', data_schema=vol.Schema(fields)
        )

    async def async_step_link(self, user_input=None):
        """Request Z-Wave data from the user."""
        errors = {}

        if user_input is not None:
            return self.async_create_entry(
                title="Z-Wave",
                data={
                    CONF_USB_STICK_PATH: user_input[CONF_USB_STICK_PATH],
                    CONF_NETWORK_KEY: user_input[CONF_NETWORK_KEY],
                    CONF_AUTOHEAL: user_input[CONF_AUTOHEAL],
                    CONF_POLLING_INTERVAL: user_input[CONF_POLLING_INTERVAL]
                },
            )

        return self.async_show_form(
            step_id='link',
            errors=errors,
        )

    async def async_step_import(self, info):
        """Import existing configuration from Z-Wave."""
        if self.hass.config_entries.async_entries(DOMAIN):
            return self.async_abort(reason='already_setup')

        return self.async_create_entry(
            title="Z-Wave (import from configuration.yaml)",
            data={
                CONF_USB_STICK_PATH: info.get(CONF_USB_STICK_PATH),
                CONF_NETWORK_KEY: info.get(CONF_NETWORK_KEY),
                CONF_AUTOHEAL: info.get(CONF_AUTOHEAL),
                CONF_POLLING_INTERVAL: info.get(CONF_POLLING_INTERVAL)
            },
        )
