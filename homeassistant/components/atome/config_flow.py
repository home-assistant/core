"""Define a config flow manager for KeyAtome."""
import logging

# HA library
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_NAME, CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import config_validation as cv

# from pykeyatome
from pykeyatome.client import AtomeClient

# component library
from .const import (
    CONF_ATOME_LINKY_NUMBER,
    DEFAULT_ATOME_LINKY_NUMBER,
    DEFAULT_NAME,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

KEY_ATOME_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(
            CONF_ATOME_LINKY_NUMBER, default=DEFAULT_ATOME_LINKY_NUMBER
        ): cv.positive_int,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


@config_entries.HANDLERS.register(DOMAIN)
class KeyAtomeFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a KeyAtome config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def _perform_login(self, username, password, atome_linky_number):
        atome_client = AtomeClient(username, password, atome_linky_number)
        login_value = await self.hass.async_add_executor_job(atome_client.login)
        if login_value is None:
            _LOGGER.error("KeyAtome Config Flow : No login available for atome server")
        return login_value

    async def async_step_user(self, user_input=None):
        """Handle the start of the config flow."""
        if not user_input:
            return self.async_show_form(
                step_id="user", data_schema=KEY_ATOME_DATA_SCHEMA
            )
        # Set username / password / atome_linky_number
        username = user_input[CONF_USERNAME]
        password = user_input[CONF_PASSWORD]
        atome_linky_number = user_input.get(
            CONF_ATOME_LINKY_NUMBER, DEFAULT_ATOME_LINKY_NUMBER
        )

        # compunte unique id
        if atome_linky_number == 1:
            config_id = str(username)
        else:
            config_id = str(username) + "_linky_" + str(atome_linky_number)

        await self.async_set_unique_id(config_id)
        self._abort_if_unique_id_configured()

        # check if login is ok
        login_result = await self._perform_login(username, password, atome_linky_number)

        if login_result is None:
            return self.async_show_form(
                step_id="user",
                data_schema=KEY_ATOME_DATA_SCHEMA,
                errors={"base": "invalid_credentials"},
            )

        return self.async_create_entry(
            title=f"KeyAtome ({config_id})",
            data=user_input,
        )
