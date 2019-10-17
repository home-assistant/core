"""Config flow for solarlog integration."""
from requests.exceptions import HTTPError, Timeout
from sunwatcher.solarlog.solarlog import SolarLog
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.util import slugify

from .const import DEFAULT_HOST, DEFAULT_NAME, DOMAIN


@callback
def solarlog_entries(hass: HomeAssistant):
    """Return the hosts already configured."""
    return set(
        entry.data[CONF_HOST] for entry in hass.config_entries.async_entries(DOMAIN)
    )


class SolarLogConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for solarlog."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._errors = {}

    def _host_in_configuration_exists(self, user_input) -> bool:
        """Return True if host exists in configuration."""
        host = user_input.get(CONF_HOST, DEFAULT_HOST)
        if host in solarlog_entries(self.hass):
            return True
        return False

    async def _test_connection(self, user_input=None):
        """Check if we can connect to the Solar-Log device."""
        host = user_input.get(CONF_HOST, DEFAULT_HOST)
        try:
            SolarLog(f"http://{host}")
            return True
        except (OSError, HTTPError, Timeout):
            self._errors[CONF_HOST] = "cannot_connect"
        return False

    async def async_step_user(self, user_input=None):
        """Step when user intializes a integration."""
        self._errors = {}
        if user_input is not None:
            # set some defaults in case we need to return to the form
            if self._host_in_configuration_exists(user_input):
                self._errors[CONF_HOST] = "already_configured"
            else:
                if await self._test_connection(user_input):
                    name = slugify(user_input.get(CONF_NAME, DEFAULT_NAME))
                    host = user_input.get(CONF_HOST, DEFAULT_HOST)
                    return self.async_create_entry(title=name, data={CONF_HOST: host})
        else:
            user_input = {}
            user_input[CONF_NAME] = DEFAULT_NAME
            user_input[CONF_HOST] = DEFAULT_HOST

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_NAME, default=user_input.get(CONF_NAME, DEFAULT_NAME)
                    ): str,
                    vol.Required(
                        CONF_HOST, default=user_input.get(CONF_HOST, DEFAULT_HOST)
                    ): str,
                }
            ),
            errors=self._errors,
        )

    async def async_step_import(self, user_input=None):
        """Import a config entry."""
        if self._host_in_configuration_exists(user_input):
            return self.async_abort(reason="already_configured")
        return await self.async_step_user(user_input)
