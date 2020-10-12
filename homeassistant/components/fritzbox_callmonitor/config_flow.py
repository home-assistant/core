"""Config flow for fritzbox_callmonitor."""

from fritzconnection.core.exceptions import FritzConnectionException
import requests
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME

from .base import FritzBoxPhonebook

# pylint:disable=unused-import
from .const import (
    CONF_PHONEBOOK,
    CONF_PREFIXES,
    DEFAULT_HOST,
    DEFAULT_PHONEBOOK,
    DEFAULT_PORT,
    DEFAULT_USERNAME,
    DOMAIN,
)

DATA_SCHEMA_USER = vol.Schema(
    {
        vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): vol.Coerce(int),
        vol.Required(CONF_USERNAME, default=DEFAULT_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_PHONEBOOK, default=DEFAULT_PHONEBOOK): int,
        vol.Optional(CONF_PREFIXES): str,
    }
)

RESULT_INVALID_AUTH = "invalid_auth"
RESULT_NO_DEVIES_FOUND = "no_devices_found"
RESULT_NOT_SUPPORTED = "not_supported"
RESULT_SUCCESS = "success"


class FritzBoxCallMonitorConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a fritzbox_callmonitor config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize flow."""
        self._name = None
        self._host = None
        self._port = None
        self._username = None
        self._password = None
        self._phonebook_id = None
        self._prefixes = None

    def _get_entry(self):
        """Create and return an entry."""
        return self.async_create_entry(
            title=self._name,
            data={
                CONF_HOST: self._host,
                CONF_PORT: self._port,
                CONF_USERNAME: self._username,
                CONF_PASSWORD: self._password,
                CONF_PHONEBOOK: self._phonebook_id,
                CONF_PREFIXES: self._prefixes,
            },
        )

    def _try_connect(self):
        """Try to connect and check auth."""
        phonebook = FritzBoxPhonebook(
            host=self._host,
            port=self._port,
            username=self._username,
            password=self._password,
            phonebook_id=self._phonebook_id,
            prefixes=self._prefixes,
        )

        try:
            phonebook.init_phonebook()
            return RESULT_SUCCESS
        except FritzConnectionException:
            return RESULT_INVALID_AUTH
        except requests.exceptions.ConnectionError:
            return RESULT_NO_DEVIES_FOUND
        except ValueError:
            return RESULT_NOT_SUPPORTED

    async def async_step_import(self, user_input=None):
        """Handle configuration by yaml file."""
        return await self.async_step_user(user_input)

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is not None:

            for entry in self.hass.config_entries.async_entries(DOMAIN):
                if (
                    entry.data[CONF_HOST] == user_input[CONF_HOST]
                    and entry.data[CONF_PHONEBOOK] == user_input[CONF_PHONEBOOK]
                ):
                    return self.async_abort(reason="already_configured")

            self._name = user_input[CONF_HOST]
            self._host = user_input[CONF_HOST]
            self._port = user_input[CONF_PORT]
            self._password = user_input[CONF_PASSWORD]
            self._username = user_input[CONF_USERNAME]
            self._phonebook_id = user_input[CONF_PHONEBOOK]
            self._prefixes = user_input.get(CONF_PREFIXES)

            if self._prefixes and self._prefixes.strip():
                self._prefixes = [
                    prefix.strip() for prefix in self._prefixes.split(",")
                ]

            result = await self.hass.async_add_executor_job(self._try_connect)

            if result == RESULT_SUCCESS:
                return self._get_entry()
            if result != RESULT_INVALID_AUTH:
                return self.async_abort(reason=result)
            errors["base"] = result

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA_USER, errors=errors
        )
