"""Config flow to configure Z-Wave."""
from collections import OrderedDict
import logging

import voluptuous as vol

from homeassistant import config_entries

from .const import (
    CONF_USB_STICK_PATH, CONF_NETWORK_KEY,
    DEFAULT_CONF_USB_STICK_PATH, DOMAIN)

_LOGGER = logging.getLogger(__name__)


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
        if self._async_current_entries():
            return self.async_abort(reason='one_instance_only')

        if user_input is not None:
            return self.async_create_entry(
                title="Z-Wave",
                data={
                    CONF_USB_STICK_PATH: user_input[CONF_USB_STICK_PATH],
                    CONF_NETWORK_KEY: user_input[CONF_NETWORK_KEY],
                },
            )

        fields = OrderedDict()
        fields[vol.Required(CONF_USB_STICK_PATH,
                            default=DEFAULT_CONF_USB_STICK_PATH)] = str
        fields[vol.Optional(CONF_NETWORK_KEY)] = str

        return self.async_show_form(
            step_id='init', data_schema=vol.Schema(fields)
        )

    async def async_step_import(self, info):
        """Import existing configuration from Z-Wave."""
        if self._async_current_entries():
            return self.async_abort(reason='already_setup')

        return self.async_create_entry(
            title="Z-Wave (import from configuration.yaml)",
            data={
                CONF_USB_STICK_PATH: info.get(CONF_USB_STICK_PATH),
                CONF_NETWORK_KEY: info.get(CONF_NETWORK_KEY),
            },
        )
