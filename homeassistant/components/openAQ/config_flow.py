"""Adds config flow for OpenAQ."""

from .const import (
    SENSOR_ID,
    DEFAULT_SENSOR_ID,
    DOMAIN
    )

from homeassistant import config_entries
import voluptuous as vol


STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(SENSOR_ID, default=DEFAULT_SENSOR_ID): str,
    }
)

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for OpenAQ."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    def __init__(self):
        """Initialize."""
        self._data = {}

    async def async_step_user(self, user_input=None):
        """Handle user initiated configuration."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Todo: validate the user input
            self._data = user_input
            # self._data[CONF_MONITORED_VARIABLES] = DEFAULT_MONITORED_VARIABLES
            return self.async_create_entry(title=self._data[SENSOR_ID], data=self._data)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
