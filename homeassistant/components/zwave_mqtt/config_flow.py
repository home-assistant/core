"""Config flow for zwave_mqtt integration."""
import logging

from homeassistant import config_entries

from .const import DOMAIN  # pylint:disable=unused-import

_LOGGER = logging.getLogger(__name__)

TITLE = "Z-Wave MQTT"


class DomainConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for zwave_mqtt."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        return self.async_create_entry(title=TITLE, data={})
