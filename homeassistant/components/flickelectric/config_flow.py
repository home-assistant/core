"""Config Flow for Flick Electric integration."""
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_PASSWORD,
    CONF_USERNAME,
)

from .const import DOMAIN

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_CLIENT_ID): str,
        vol.Optional(CONF_CLIENT_SECRET): str,
    }
)


class FlickConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Flick config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def async_step_user(self, config):
        """Handle gathering login info."""
        if config is not None:
            # TODO: Validate Login

            await self.async_set_unique_id(f"flickelectric_{config[CONF_USERNAME]}")
            self._abort_if_unique_id_configured()

            return self.async_create_entry(title="Flick Electric", data=config)

        return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA)
