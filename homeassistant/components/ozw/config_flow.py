"""Config flow for ozw integration."""
from homeassistant import config_entries

from .const import DOMAIN  # pylint:disable=unused-import

TITLE = "OpenZWave"


class DomainConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ozw."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        if "mqtt" not in self.hass.config.components:
            return self.async_abort(reason="mqtt_required")
        if user_input is not None:
            return self.async_create_entry(title=TITLE, data={})

        return self.async_show_form(step_id="user")
