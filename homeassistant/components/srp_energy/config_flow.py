"""Config flow for SRP Energy."""
import logging

import voluptuous as vol
from srpenergy.client import SrpEnergyClient

from homeassistant import config_entries, core, exceptions
from homeassistant.const import CONF_NAME, CONF_PASSWORD, CONF_USERNAME, CONF_ID

from .const import DOMAIN, DEFAULT_NAME  # pylint:disable=unused-import

_LOGGER = logging.getLogger(__name__)

# DATA_SCHEMA = vol.Schema({"username": str, "password": str, "id": str})
DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ID): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
    }
)


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    try:
        srp_client = SrpEnergyClient(
            data[CONF_ID], data[CONF_USERNAME], data[CONF_PASSWORD]
        )

        is_valid = await hass.async_add_executor_job(srp_client.validate)

        if is_valid:
            return True
        else:
            raise InvalidAuth

    except ValueError:
        raise CannotConnect


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SRP Energy."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def async_step_user(self, user_input=None):
        """
        Handle a flow initialized by the user.

        user_input is a dict with keys defined in DATA_SCHEMA
        with values provided by the user.
        """
        errors = {}

        if self._async_current_entries():
            return self.async_abort(reason="one_instance_allowed")

        if user_input is not None:
            try:

                await validate_input(self.hass, user_input)
                return self.async_create_entry(
                    title=user_input[CONF_NAME], data=user_input
                )

            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        # Show a form to capture config settings from user
        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_import(self, import_config):
        """Import from config."""
        # Validate config values
        return await self.async_step_user(user_input=import_config)


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
