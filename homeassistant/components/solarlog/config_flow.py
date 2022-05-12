"""Config flow for solarlog integration."""
import logging
from urllib.parse import ParseResult, urlparse

from requests.exceptions import HTTPError, Timeout
from sunwatcher.solarlog.solarlog import SolarLog
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.util import slugify

from .const import DEFAULT_HOST, DEFAULT_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)


@callback
def solarlog_entries(hass: HomeAssistant):
    """Return the hosts already configured."""
    return {
        entry.data[CONF_HOST] for entry in hass.config_entries.async_entries(DOMAIN)
    }


class SolarLogConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for solarlog."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._errors: dict = {}

    def _host_in_configuration_exists(self, host) -> bool:
        """Return True if host exists in configuration."""
        if host in solarlog_entries(self.hass):
            return True
        return False

    async def _test_connection(self, host):
        """Check if we can connect to the Solar-Log device."""
        try:
            await self.hass.async_add_executor_job(SolarLog, host)
            return True
        except (OSError, HTTPError, Timeout):
            self._errors[CONF_HOST] = "cannot_connect"
            _LOGGER.error(
                "Could not connect to Solar-Log device at %s, check host ip address",
                host,
            )
        return False

    async def async_step_user(self, user_input=None):
        """Step when user initializes a integration."""
        self._errors = {}
        if user_input is not None:
            # set some defaults in case we need to return to the form
            name = slugify(user_input.get(CONF_NAME, DEFAULT_NAME))
            host_entry = user_input.get(CONF_HOST, DEFAULT_HOST)

            url = urlparse(host_entry, "http")
            netloc = url.netloc or url.path
            path = url.path if url.netloc else ""
            url = ParseResult("http", netloc, path, *url[3:])
            host = url.geturl()

            if self._host_in_configuration_exists(host):
                self._errors[CONF_HOST] = "already_configured"
            else:
                if await self._test_connection(host):
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
        host_entry = user_input.get(CONF_HOST, DEFAULT_HOST)

        url = urlparse(host_entry, "http")
        netloc = url.netloc or url.path
        path = url.path if url.netloc else ""
        url = ParseResult("http", netloc, path, *url[3:])
        host = url.geturl()

        if self._host_in_configuration_exists(host):
            return self.async_abort(reason="already_configured")
        return await self.async_step_user(user_input)
