"""Config flow for solax integration."""
import logging

from solax import real_time_api
from solax.inverter import DiscoveryError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD, CONF_PORT
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DEFAULT_PORT = 80
DEFAULT_PASSWORD = ""

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_IP_ADDRESS): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_PASSWORD, default=DEFAULT_PASSWORD): cv.string,
    }
)


async def validate_api(data):
    """Validate the credentials."""

    api = await real_time_api(
        data[CONF_IP_ADDRESS], data[CONF_PORT], data[CONF_PASSWORD]
    )
    resp = await api.get_data()
    return resp.serial_number


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Solax."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
            )

        try:
            serial_number = await validate_api(user_input)
            return self.async_create_entry(title=serial_number, data=user_input)
        except (ConnectionError, DiscoveryError):
            errors["base"] = "cannot_connect"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_import(self, config):
        """Handle import of solax config from YAML."""

        import_data = {
            CONF_IP_ADDRESS: config[CONF_IP_ADDRESS],
            CONF_PORT: config[CONF_PORT],
            CONF_PASSWORD: "",
        }

        _LOGGER.warning(
            "Please remove your solax configuration from YAML as it will be removed in a future version"
        )

        return await self.async_step_user(user_input=import_data)
