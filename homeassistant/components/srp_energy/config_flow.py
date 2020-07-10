"""Config flow for SRP Energy integration."""
import logging

import voluptuous as vol
from srpenergy.client import SrpEnergyClient

from homeassistant import config_entries, core, exceptions
from homeassistant.const import CONF_NAME, CONF_PASSWORD, CONF_USERNAME, CONF_ID
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN, DEFAULT_NAME  # pylint:disable=unused-import

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema({"username": str, "password": str, "id": str})
DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ID): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
    }
)


# class PlaceholderHub:
#     """Placeholder class to make tests pass.

#     TODO Remove this placeholder class and replace with things from your PyPI package.
#     """

#     def __init__(self, host):
#         """Initialize."""
#         self.host = host

#     async def authenticate(self, username, password) -> bool:
#         """Test if we can authenticate with the host."""
#         return True


def validate_srp_input(account_id, username, password):

    try:
        srp_client = SrpEnergyClient(account_id, username, password)
    except ValueError:
        raise CannotConnect

    if not srp_client.validate:
        raise InvalidAuth


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    # TODO validate the data can be used to set up a connection.

    # If your PyPI package is not built with async, pass your methods
    # to the executor:
    await hass.async_add_executor_job(
        validate_srp_input, data[CONF_ID], data[CONF_USERNAME], data[CONF_PASSWORD]
    )

    # username = data[CONF_USERNAME]
    # password = data[CONF_PASSWORD]
    # account_id = data[CONF_ID]

    # try:
    #     srp_client = SrpEnergyClient(account_id, username, password)
    # except ValueError as err:
    #     raise CannotConnect(f"Couldn't connect. {err}")

    # # hub = PlaceholderHub(data["host"])
    # if not await hass.async_add_executor_job(srp_client.validate):
    #     raise InvalidAuth

    # if not await srp_client.validate():
    #     raise InvalidAuth

    # If you cannot connect:
    # throw CannotConnect
    # If the authentication is wrong:
    # InvalidAuth

    # Return info that you want to store in the config entry.
    return {CONF_NAME: data[CONF_NAME]}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SRP Energy."""

    VERSION = 1
    # TODO pick one of the available connection classes in homeassistant/config_entries.py
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        if self._async_current_entries():
            return self.async_abort(reason="one_instance_allowed")

        errors = {}
        if user_input is not None:
            try:

                info = await validate_input(self.hass, user_input)

                return self.async_create_entry(title=info[CONF_NAME], data=user_input)

            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_import(self, import_config):
        """Import from config."""
        # Validate config values
        # return self.async_abort(reason="wrong_server_id")

        return await self.async_step_user(user_input=import_config)


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
