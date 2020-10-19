"""Config flow for fritzbox_callmonitor."""

from functools import partial

from fritzconnection import FritzConnection
from fritzconnection.core.exceptions import FritzConnectionException, FritzSecurityError
from requests.exceptions import ConnectionError as RequestsConnectionError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import callback

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
    FRITZ_ACTION_GET_INFO,
    FRITZ_ATTR_NAME,
    FRITZ_ATTR_SERIAL_NUMBER,
    FRITZ_SERVICE_DEVICE_INFO,
    SERIAL_NUMBER,
)

DATA_SCHEMA_USER = vol.Schema(
    {
        vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): vol.Coerce(int),
        vol.Required(CONF_USERNAME, default=DEFAULT_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)

RESULT_INVALID_AUTH = "invalid_auth"
RESULT_INSUFFICIENT_PERMISSIONS = "insufficient_permissions"
RESULT_NO_DEVIES_FOUND = "no_devices_found"
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
        self._phonebook_name = None
        self._phonebook_id = None
        self._phonebook_ids = None
        self._phonebook = None
        self._prefixes = None
        self._serial_number = None

    def _get_entry(self):
        """Create and return an entry."""
        return self.async_create_entry(
            title=self._phonebook_name,
            data={
                CONF_HOST: self._host,
                CONF_PORT: self._port,
                CONF_USERNAME: self._username,
                CONF_PASSWORD: self._password,
                CONF_PHONEBOOK: self._phonebook_id,
                CONF_PREFIXES: self._prefixes,
                SERIAL_NUMBER: self._serial_number,
            },
        )

    def _try_connect(self):
        """Try to connect and check auth."""
        self._phonebook = FritzBoxPhonebook(
            host=self._host,
            username=self._username,
            password=self._password,
            phonebook_id=self._phonebook_id,
            prefixes=self._prefixes,
        )

        try:
            self._phonebook.init_phonebook()
            self._phonebook_ids = self._phonebook.get_phonebook_ids()

            fritz_connection = FritzConnection(
                address=self._host, user=self._username, password=self._password
            )
            device_info = fritz_connection.call_action(
                FRITZ_SERVICE_DEVICE_INFO, FRITZ_ACTION_GET_INFO
            )
            self._serial_number = device_info[FRITZ_ATTR_SERIAL_NUMBER]

            return RESULT_SUCCESS
        except RequestsConnectionError:
            return RESULT_NO_DEVIES_FOUND
        except FritzSecurityError:
            return RESULT_INSUFFICIENT_PERMISSIONS
        except FritzConnectionException:
            return RESULT_INVALID_AUTH

    def _is_already_configured(self, host, phonebook_id):
        """Check if an entity with the same host and phonebook_id is already configured."""
        for entry in self.hass.config_entries.async_entries(DOMAIN):
            if (
                entry.data[CONF_HOST] == host
                and entry.data[CONF_PHONEBOOK] == phonebook_id
            ):
                return True

    async def _get_name_of_phonebook(self, phonebook_id):
        """Return name of phonebook for given phonebook_id."""
        phonebook_info = await self.hass.async_add_executor_job(
            partial(self._phonebook.fph.phonebook_info, phonebook_id)
        )
        return phonebook_info[FRITZ_ATTR_NAME]

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return FritzBoxCallMonitorOptionsFlowHandler(config_entry)

    async def async_step_import(self, user_input=None):
        """Handle configuration by yaml file."""
        return await self.async_step_user(user_input)

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is not None:

            self._name = user_input[CONF_HOST]
            self._host = user_input[CONF_HOST]
            self._port = user_input[CONF_PORT]
            self._password = user_input[CONF_PASSWORD]
            self._username = user_input[CONF_USERNAME]

            result = await self.hass.async_add_executor_job(self._try_connect)

            if result == RESULT_SUCCESS:
                if len(self._phonebook_ids) > 1:
                    return await self.async_step_phonebook()

                self._phonebook_id = DEFAULT_PHONEBOOK
                self._phonebook_name = await self._get_name_of_phonebook(
                    self._phonebook_id
                )

                if self._is_already_configured(self._host, self._phonebook_id):
                    return self.async_abort(reason="already_configured")

                return self._get_entry()
            if result != RESULT_INVALID_AUTH:
                return self.async_abort(reason=result)
            errors["base"] = result

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA_USER, errors=errors
        )

    async def async_step_phonebook(self, user_input=None):
        """Handle a flow to chose one of multiple available phonebooks."""
        errors = {}
        phonebooks = []

        for phonebook_id in self._phonebook_ids:
            phonebooks.append(await self._get_name_of_phonebook(phonebook_id))

        if user_input is not None:
            phonebook_name = user_input[CONF_PHONEBOOK]
            phonebook_id = phonebooks.index(phonebook_name)

            self._phonebook_name = phonebook_name
            self._phonebook_id = phonebook_id

            if self._is_already_configured(self._host, self._phonebook_id):
                return self.async_abort(reason="already_configured")

            return self._get_entry()

        return self.async_show_form(
            step_id="phonebook",
            data_schema=vol.Schema({vol.Required(CONF_PHONEBOOK): vol.In(phonebooks)}),
            errors=errors,
        )


class FritzBoxCallMonitorOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a fritzbox_callmonitor options flow."""

    def __init__(self, config_entry):
        """Initialize."""
        self.config_entry = config_entry
        self._prefixes = None

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:

            self._prefixes = user_input.get(CONF_PREFIXES)

            if self._prefixes and self._prefixes.strip():
                self._prefixes = [
                    prefix.strip() for prefix in self._prefixes.split(",")
                ]

            return self.async_create_entry(
                title="", data={CONF_PREFIXES: self._prefixes}
            )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_PREFIXES,
                        default=self.config_entry.options.get(CONF_PREFIXES),
                    ): str,
                }
            ),
        )
