"""Config flow to configure the Ecovacs integration."""
import random
import string

import requests
from sucks import EcoVacsAPI
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

# pylint:disable=unused-import
from .const import CONF_CONTINENT, CONF_COUNTRY, CONF_DEVICE_ID, DOMAIN

DATA_SCHEMA_USER = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(CONF_COUNTRY): vol.All(str, vol.Lower),
        vol.Required(CONF_CONTINENT): vol.All(str, vol.Lower),
    }
)

RESULT_SUCCESS = "success"
RESULT_INVALID_AUTH = "invalid_auth"
RESULT_LOCATION_NOT_FOUND = "location_not_found"
RESULT_NOT_FOUND = "not_found"


class EcovacsConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Ecovacs config flow."""

    def __init__(self):
        """Initialize flow."""
        self._username = None
        self._password = None
        self._country = None
        self._continent = None
        self._device_id = None

    @classmethod
    def _generate_random_device_id(self):
        """Generate a random device ID."""
        return "".join(
            random.choice(string.ascii_uppercase + string.digits) for _ in range(8)
        )

    def _try_connect(self):
        """Try to connect and check auth."""
        try:
            ecovacs_api = EcoVacsAPI(
                self._device_id,
                self._username,
                EcoVacsAPI.md5(self._password),
                self._country,
                self._continent,
            )
            if not ecovacs_api.devices():
                return RESULT_NOT_FOUND
            return RESULT_SUCCESS
        except requests.exceptions.ConnectionError:
            return RESULT_LOCATION_NOT_FOUND
        except ValueError:
            return RESULT_INVALID_AUTH

    def _get_entry(self):
        """Create and return an entry."""
        return self.async_create_entry(
            title=self._username,
            data={
                CONF_USERNAME: self._username,
                CONF_PASSWORD: self._password,
                CONF_COUNTRY: self._country,
                CONF_CONTINENT: self._continent,
                CONF_DEVICE_ID: self._device_id,
            },
        )

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is not None:

            for entry in self.hass.config_entries.async_entries(DOMAIN):
                if entry.data[CONF_USERNAME] == user_input[CONF_USERNAME]:
                    return self.async_abort(reason="already_configured")

            self._username = user_input[CONF_USERNAME]
            self._password = user_input[CONF_PASSWORD]
            self._country = user_input[CONF_COUNTRY]
            self._continent = user_input[CONF_CONTINENT]
            self._device_id = self._generate_random_device_id()

            result = await self.hass.async_add_executor_job(self._try_connect)

            if result == RESULT_SUCCESS:
                return self._get_entry()
            if result != RESULT_INVALID_AUTH:
                return self.async_abort(reason=result)
            errors["base"] = result

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA_USER, errors=errors
        )
