"""Config flow to configure Matrix Bot."""
import functools
import logging

from matrix_client.client import MatrixClient, MatrixRequestError
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, CONF_VERIFY_SSL

from .const import CONF_HOMESERVER, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    client = MatrixClient(
        base_url=data[CONF_HOMESERVER], valid_cert_check=data[CONF_VERIFY_SSL],
    )
    try:
        await hass.async_add_executor_job(
            functools.partial(client.login, data[CONF_USERNAME], data[CONF_PASSWORD],)
        )
    except MatrixRequestError:
        raise InvalidAuth

    return {"title": f"{data[CONF_USERNAME]} at {data[CONF_HOMESERVER]}"}


class MatrixConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Matrix config flow."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        errors = {}
        data_schema = vol.Schema(
            {
                vol.Required(CONF_HOMESERVER): str,
                vol.Optional(CONF_VERIFY_SSL, default=True): bool,
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
            }
        )
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_USERNAME])
            self._abort_if_unique_id_configured()

            try:
                info = await validate_input(self.hass, user_input)

                return self.async_create_entry(title=info["title"], data=user_input)
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

    async def async_step_import(self, import_config):
        """Import a config entry from configuration.yaml."""
        return await self.async_step_user(import_config)


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
