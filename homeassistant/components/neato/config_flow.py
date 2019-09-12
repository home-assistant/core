"""Config flow to configure Neato integration."""

import logging
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback

from .const import DOMAIN, CONF_VENDOR, VALID_VENDORS


DOCS_URL = "https://www.home-assistant.io/components/neato"
DEFAULT_VENDOR = "neato"

_LOGGER = logging.getLogger(__name__)


@callback
def configured_neato(hass):
    """Return the configured Neato Account."""
    entries = hass.config_entries.async_entries(DOMAIN)
    if entries:
        return entries[0]
    return None


@config_entries.HANDLERS.register(DOMAIN)
class NeatoConfigFlow(config_entries.ConfigFlow):
    """Neato integration config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize flow."""
        self._username = vol.UNDEFINED
        self._password = vol.UNDEFINED
        self._vendor = vol.UNDEFINED

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        errors = {}

        if configured_neato(self.hass) is not None:
            return self.async_abort(reason="already_configured")

        if user_input is not None:
            self._username = user_input["username"]
            self._password = user_input["password"]
            self._vendor = user_input["vendor"]

            error = self.try_login(self._username, self._password, self._vendor)
            if error:
                errors["base"] = error
            else:
                return self.async_create_entry(
                    title=user_input[CONF_USERNAME],
                    data=user_input,
                    description_placeholders={"docs_url": DOCS_URL},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Optional(CONF_VENDOR, default="neato"): vol.In(VALID_VENDORS),
                }
            ),
            description_placeholders={"docs_url": DOCS_URL},
            errors=errors,
        )

    async def async_step_import(self, user_input):
        """Import a config flow from configuration."""
        username = user_input[CONF_USERNAME]
        password = user_input[CONF_PASSWORD]
        vendor = user_input[CONF_VENDOR]

        error = self.try_login(username, password, vendor)
        if error is not None:
            _LOGGER.error(error)
            return self.async_abort(reason=error)

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
        if vendor == "vorwerk":
            this_vendor = Vorwerk()
        elif vendor == "neato":
            this_vendor = Neato()
        else:
            # You have to set a valid vendor
            return "invalid_vendor"

        try:
            Account(username, password, this_vendor)
        except HTTPError:
            return "invalid_credentials"

        return None
