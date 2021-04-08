"""Config flow for fritzbox_callmonitor."""

from fritzconnection import FritzConnection
from fritzconnection.core.exceptions import FritzConnectionException, FritzSecurityError
from requests.exceptions import ConnectionError as RequestsConnectionError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)
from homeassistant.core import callback

from .base import FritzBoxPhonebook
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
RESULT_MALFORMED_PREFIXES = "malformed_prefixes"
RESULT_NO_DEVIES_FOUND = "no_devices_found"
RESULT_SUCCESS = "success"


class FritzBoxCallMonitorConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a fritzbox_callmonitor config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize flow."""
        self._host = None
        self._port = None
        self._username = None
        self._password = None
        self._phonebook_name = None
        self._phonebook_names = None
        self._phonebook_id = None
        self._phonebook_ids = None
        self._fritzbox_phonebook = None
        self._prefixes = None
        self._serial_number = None

    def _get_config_entry(self):
        """Create and return an config entry."""
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
        self._fritzbox_phonebook = FritzBoxPhonebook(
            host=self._host,
            username=self._username,
            password=self._password,
            phonebook_id=self._phonebook_id,
            prefixes=self._prefixes,
        )

        try:
            self._fritzbox_phonebook.init_phonebook()
            self._phonebook_ids = self._fritzbox_phonebook.get_phonebook_ids()

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

    async def _get_name_of_phonebook(self, phonebook_id):
        """Return name of phonebook for given phonebook_id."""
        phonebook_info = await self.hass.async_add_executor_job(
            self._fritzbox_phonebook.fph.phonebook_info, phonebook_id
        )
        return phonebook_info[FRITZ_ATTR_NAME]

    async def _get_list_of_phonebook_names(self):
        """Return list of names for all available phonebooks."""
        phonebook_names = []

        for phonebook_id in self._phonebook_ids:
            phonebook_names.append(await self._get_name_of_phonebook(phonebook_id))

        return phonebook_names

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

        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=DATA_SCHEMA_USER, errors={}
            )

        self._host = user_input[CONF_HOST]
        self._port = user_input[CONF_PORT]
        self._password = user_input[CONF_PASSWORD]
        self._username = user_input[CONF_USERNAME]

        result = await self.hass.async_add_executor_job(self._try_connect)

        if result == RESULT_INVALID_AUTH:
            return self.async_show_form(
                step_id="user",
                data_schema=DATA_SCHEMA_USER,
                errors={"base": RESULT_INVALID_AUTH},
            )

        if result != RESULT_SUCCESS:
            return self.async_abort(reason=result)

        if self.context["source"] == config_entries.SOURCE_IMPORT:
            self._phonebook_id = user_input[CONF_PHONEBOOK]
            self._phonebook_name = user_input[CONF_NAME]

        elif len(self._phonebook_ids) > 1:
            return await self.async_step_phonebook()

        else:
            self._phonebook_id = DEFAULT_PHONEBOOK
            self._phonebook_name = await self._get_name_of_phonebook(self._phonebook_id)

        await self.async_set_unique_id(f"{self._serial_number}-{self._phonebook_id}")
        self._abort_if_unique_id_configured()

        return self._get_config_entry()

    async def async_step_phonebook(self, user_input=None):
        """Handle a flow to chose one of multiple available phonebooks."""

        if self._phonebook_names is None:
            self._phonebook_names = await self._get_list_of_phonebook_names()

        if user_input is None:
            return self.async_show_form(
                step_id="phonebook",
                data_schema=vol.Schema(
                    {vol.Required(CONF_PHONEBOOK): vol.In(self._phonebook_names)}
                ),
                errors={},
            )

        self._phonebook_name = user_input[CONF_PHONEBOOK]
        self._phonebook_id = self._phonebook_names.index(self._phonebook_name)

        await self.async_set_unique_id(f"{self._serial_number}-{self._phonebook_id}")
        self._abort_if_unique_id_configured()

        return self._get_config_entry()


class FritzBoxCallMonitorOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a fritzbox_callmonitor options flow."""

    def __init__(self, config_entry):
        """Initialize."""
        self.config_entry = config_entry

    @classmethod
    def _are_prefixes_valid(cls, prefixes):
        """Check if prefixes are valid."""
        return prefixes.strip() if prefixes else prefixes is None

    @classmethod
    def _get_list_of_prefixes(cls, prefixes):
        """Get list of prefixes."""
        if prefixes is None:
            return None
        return [prefix.strip() for prefix in prefixes.split(",")]

    def _get_option_schema_prefixes(self):
        """Get option schema for entering prefixes."""
        return vol.Schema(
            {
                vol.Optional(
                    CONF_PREFIXES,
                    description={
                        "suggested_value": self.config_entry.options.get(CONF_PREFIXES)
                    },
                ): str
            }
        )

    async def async_step_init(self, user_input=None):
        """Manage the options."""

        option_schema_prefixes = self._get_option_schema_prefixes()

        if user_input is None:
            return self.async_show_form(
                step_id="init",
                data_schema=option_schema_prefixes,
                errors={},
            )

        prefixes = user_input.get(CONF_PREFIXES)

        if not self._are_prefixes_valid(prefixes):
            return self.async_show_form(
                step_id="init",
                data_schema=option_schema_prefixes,
                errors={"base": RESULT_MALFORMED_PREFIXES},
            )

        return self.async_create_entry(
            title="", data={CONF_PREFIXES: self._get_list_of_prefixes(prefixes)}
        )
