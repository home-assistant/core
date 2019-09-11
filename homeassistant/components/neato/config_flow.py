"""Config flow to configure Neato integration."""

from collections import OrderedDict
import logging
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from .const import DOMAIN, CONF_VENDOR


DOCS_URL = "https://www.home-assistant.io/components/neato"

_LOGGER = logging.getLogger(__name__)


@config_entries.HANDLERS.register(DOMAIN)
class NeatoConfigFlow(config_entries.ConfigFlow):
    """Neato integration config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    def __init__(self):
        """Initialize flow."""
        self._username = vol.UNDEFINED
        self._password = vol.UNDEFINED
        self._vendor = vol.UNDEFINED

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is not None:
            self._username = user_input["username"]
            self._password = user_input["password"]
            self._vendor = user_input["vendor"]

            error = self.try_login(self._username, self._password, self._vendor)
            if error:
                errors["base"] = error
            else:
                return self.async_create_entry(
                    title=self._username,
                    data={
                        CONF_USERNAME: self._username,
                        CONF_PASSWORD: self._password,
                        CONF_VENDOR: self._vendor,
                    },
                    description_placeholders={"docs_url": DOCS_URL},
                )

        data_schema = OrderedDict()
        data_schema[vol.Required(CONF_USERNAME, default=self._username)] = str
        data_schema[vol.Required(CONF_PASSWORD, default=self._password)] = str
        data_schema[vol.Optional(CONF_VENDOR, default=self._vendor)] = str

        return self.async_create_entry(
            title=self._username,
            data={
                CONF_USERNAME: self._username,
                CONF_PASSWORD: self._password,
                CONF_VENDOR: self._vendor,
            },
            description_placeholders={"docs_url": DOCS_URL},
        )

    async def async_step_import(self, user_input):
        """Import a config flow from configuration."""
        username = user_input[CONF_USERNAME]
        password = user_input[CONF_PASSWORD]
        vendor = user_input[CONF_VENDOR]

        error = self.try_login(username, password, vendor)
        if error is not None:
            _LOGGER.error("Invalid credentials for %s", username)
            return self.async_abort(reason="invalid_credentials")
        return self.async_create_entry(
            title=f"{username} (from configuration)",
            data={
                CONF_USERNAME: username,
                CONF_PASSWORD: password,
                CONF_VENDOR: vendor,
            },
        )

    @staticmethod
    def try_login(username, password, vendor):
        """Try logging in to device and return any errors."""
        from requests.exceptions import HTTPError
        from pybotvac import Account, Neato, Vorwerk

        this_vendor = None
        if vendor == "neato":
            vendor = Neato()
        elif vendor == "vorwerk":
            vendor = Vorwerk()

        try:
            # vendor defaults to Neato()
            Account(username, password, this_vendor)
        except HTTPError:
            return "invalid_credentials"

        return None
