"""Config flow to configure Becker component."""
import logging

import voluptuous as vol

from homeassistant import config_entries

from .const import (  # pylint:disable=unused-import
    CONF_DEVICE,
    DEFAULT_CONF_USB_STICK_PATH,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class BeckerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Becker config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    def __init__(self):
        """Initialize the Becker config flow."""
        self.device = CONF_DEVICE

    async def async_step_user(self, user_input=None):
        """Handle a flow start."""
        if self._async_current_entries():
            return self.async_abort(reason="one_instance_only")

        if user_input is not None:
            return self.async_create_entry(
                title="Becker", data={CONF_DEVICE: user_input[CONF_DEVICE]}
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_DEVICE, default=DEFAULT_CONF_USB_STICK_PATH): str}
            ),
        )

    async def async_step_import(self, info):
        """Import existing configuration from Becker Cover."""
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")

        return self.async_create_entry(
            title="Becker Cover (import from configuration.yaml)",
            data={CONF_DEVICE: info.get(CONF_DEVICE)},
        )
