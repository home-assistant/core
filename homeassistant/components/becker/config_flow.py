"""Config flow to configure Becker component."""
from collections import OrderedDict
import logging

import voluptuous as vol

from homeassistant import config_entries

from .const import (
    CONF_DEVICE,
    DEFAULT_CONF_USB_STICK_PATH,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


@config_entries.HANDLERS.register(DOMAIN)
class BeckerFlowHandler(config_entries.ConfigFlow):
    """Handle a Becker config flow."""

    VERSION = 1

    def __init__(self):
        """Initialize the Becker config flow."""
        self.device = CONF_DEVICE

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        return await self.async_step_auth()

    async def async_step_user(self, user_input=None):
        """Handle a flow start."""
        if self._async_current_entries():
            return self.async_abort(reason="one_instance_only")

        fields = OrderedDict()
        fields[vol.Required(CONF_DEVICE, default=DEFAULT_CONF_USB_STICK_PATH)] = str

        return self.async_show_form(step_id="user", data_schema=vol.Schema(fields))

    async def async_step_import(self, info):
        """Import existing configuration from Becker Cover."""
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")

        return self.async_create_entry(
            title="Becker Cover (import from configuration.yaml)",
            data={
                CONF_DEVICE: info.get(CONF_DEVICE),
            },
        )
        