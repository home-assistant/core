"""Config flow for AVM Fritz!Box call monitor."""
import logging

from fritzconnection.lib.fritzphonebook import FritzPhonebook
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME

# pylint:disable=unused-import
from .const import CONF_PHONEBOOK, DEFAULT_HOST, DEFAULT_PORT, DEFAULT_USERNAME, DOMAIN

DATA_SCHEMA_USER = vol.Schema(
    {
        vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): vol.Coerce(int),
        vol.Required(CONF_USERNAME, default=DEFAULT_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_PHONEBOOK, default=0): int,
    }
)

_LOGGER = logging.getLogger(__name__)


class FritzBoxCallMonitorConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a AVM Fritz!Box call monitor config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize flow."""
        self._name = "Test name"
        self._host = None
        self._port = None
        self._password = None
        self._username = None
        self._phonebook = None

    def _get_entry(self):
        return self.async_create_entry(
            title=self._name,
            data={
                CONF_HOST: self._host,
                CONF_PORT: self._port,
                CONF_PASSWORD: self._password,
                CONF_USERNAME: self._username,
                CONF_PHONEBOOK: self._phonebook,
            },
        )

    def _try_connect(self):
        """Try to connect and check auth."""
        try:
            _LOGGER.warning("connecting...")
            phonebook = FritzPhonebook(
                address=self._host,
                user=self._username,
                password=self._password,
            )
            _LOGGER.warning("PHONEBOOK: %s", phonebook)
            return True
        except:  # noqa: E722 pylint: disable=bare-except
            return None

    async def async_step_import(self, user_input=None):
        """Handle configuration by yaml file."""
        return await self.async_step_user(user_input)

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is not None:

            for entry in self.hass.config_entries.async_entries(DOMAIN):
                if entry.data[CONF_HOST] == user_input[CONF_HOST]:
                    return self.async_abort(reason="already_configured")

            self._host = user_input[CONF_HOST]
            self._port = user_input[CONF_PORT]
            self._password = user_input[CONF_PASSWORD]
            self._username = user_input[CONF_USERNAME]
            self._phonebook = user_input[CONF_PHONEBOOK]

            _LOGGER.warning("user_input: %s", user_input)

            result = await self.hass.async_add_executor_job(self._try_connect)

            _LOGGER.warning("result: %s", result)

            if result:
                return self._get_entry()
            else:
                _LOGGER.warning("It was aborted")
                return self.async_abort(reason=result)

        _LOGGER.warning("showing gui form")
        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA_USER, errors=errors
        )
