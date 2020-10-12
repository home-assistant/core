"""Config flow for Tuya."""
import logging

from tuyaha import TuyaApi
from tuyaha.tuyaapi import TuyaAPIException, TuyaNetException, TuyaServerException
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_PLATFORM, CONF_USERNAME

# pylint:disable=unused-import
from .const import CONF_COUNTRYCODE, DOMAIN, TUYA_PLATFORMS

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA_USER = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(CONF_COUNTRYCODE): vol.Coerce(int),
        vol.Required(CONF_PLATFORM): vol.In(TUYA_PLATFORMS),
    }
)

RESULT_AUTH_FAILED = "invalid_auth"
RESULT_CONN_ERROR = "cannot_connect"
RESULT_SUCCESS = "success"

RESULT_LOG_MESSAGE = {
    RESULT_AUTH_FAILED: "Invalid credential",
    RESULT_CONN_ERROR: "Connection error",
}


class TuyaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a tuya config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize flow."""
        self._country_code = None
        self._password = None
        self._platform = None
        self._username = None
        self._is_import = False

    def _get_entry(self):
        return self.async_create_entry(
            title=self._username,
            data={
                CONF_COUNTRYCODE: self._country_code,
                CONF_PASSWORD: self._password,
                CONF_PLATFORM: self._platform,
                CONF_USERNAME: self._username,
            },
        )

    def _try_connect(self):
        """Try to connect and check auth."""
        tuya = TuyaApi()
        try:
            tuya.init(
                self._username, self._password, self._country_code, self._platform
            )
        except (TuyaNetException, TuyaServerException):
            return RESULT_CONN_ERROR
        except TuyaAPIException:
            return RESULT_AUTH_FAILED

        return RESULT_SUCCESS

    async def async_step_import(self, user_input=None):
        """Handle configuration by yaml file."""
        self._is_import = True
        return await self.async_step_user(user_input)

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        errors = {}

        if user_input is not None:

            self._country_code = str(user_input[CONF_COUNTRYCODE])
            self._password = user_input[CONF_PASSWORD]
            self._platform = user_input[CONF_PLATFORM]
            self._username = user_input[CONF_USERNAME]

            result = await self.hass.async_add_executor_job(self._try_connect)

            if result == RESULT_SUCCESS:
                return self._get_entry()
            if result != RESULT_AUTH_FAILED or self._is_import:
                if self._is_import:
                    _LOGGER.error(
                        "Error importing from configuration.yaml: %s",
                        RESULT_LOG_MESSAGE.get(result, "Generic Error"),
                    )
                return self.async_abort(reason=result)
            errors["base"] = result

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA_USER, errors=errors
        )
