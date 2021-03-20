"""Config flow for SRP Energy."""
import logging

from srpenergy.client import SrpEnergyClient
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_ID, CONF_NAME, CONF_PASSWORD, CONF_USERNAME

from .const import (  # pylint:disable=unused-import
    CONF_IS_TOU,
    DEFAULT_NAME,
    SRP_ENERGY_DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=SRP_ENERGY_DOMAIN):
    """Handle a config flow for SRP Energy."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    config = {
        vol.Required(CONF_ID): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
        vol.Optional(CONF_IS_TOU, default=False): bool,
    }

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        errors = {}

        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            try:

                srp_client = SrpEnergyClient(
                    user_input[CONF_ID],
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                )

                is_valid = await self.hass.async_add_executor_job(srp_client.validate)

                if is_valid:
                    return self.async_create_entry(
                        title=user_input[CONF_NAME], data=user_input
                    )

                errors["base"] = "invalid_auth"

            except ValueError:
                errors["base"] = "invalid_account"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=vol.Schema(self.config), errors=errors
        )

    async def async_step_import(self, import_config):
        """Import from config."""
        # Validate config values
        return await self.async_step_user(user_input=import_config)
