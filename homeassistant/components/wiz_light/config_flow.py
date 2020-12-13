"""Config flow for wiz_light."""
import logging

from srpenergy.client import SrpEnergyClient
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SRP Energy."""

    VERSION = 1
    config = {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
    }

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        errors = {}

        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            try:
                bulb = wizlight(entry.data.get(CONF_HOST))
                return self.async_create_entry(
                        title=user_input[CONF_NAME], data=user_input
                    )

            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "Cant connect to bulb!"

        return self.async_show_form(
            step_id="user", data_schema=vol.Schema(self.config), errors=errors
        )

    async def async_step_import(self, import_config):
        """Import from config."""
        # Validate config values
        return await self.async_step_user(user_input=import_config)
