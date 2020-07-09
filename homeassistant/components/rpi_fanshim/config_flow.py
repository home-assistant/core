"""Config flow for RPi Pimoroni Fan Shim integration."""
import logging

from homeassistant import config_entries

from .const import DOMAIN  # pylint:disable=unused-import

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for RPi Pimoroni Fan Shim."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_UNKNOWN

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        if user_input is None:
            user_input = {}
        return self.async_create_entry(title="RPi Pimoroni Fan Shim", data=user_input)
