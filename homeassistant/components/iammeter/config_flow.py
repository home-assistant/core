"""Config flow for iammeter integration."""
import asyncio
import logging
from urllib.parse import ParseResult, urlparse

import async_timeout
import iammeter
from iammeter.power_meter import IamMeterError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant, callback

from .const import DEFAULT_HOST, DEFAULT_NAME, DEFAULT_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORM_TIMEOUT = 8


@callback
def iammeter_entries(hass: HomeAssistant):
    """Return the hosts already configured."""
    return {
        entry.data[CONF_NAME] for entry in hass.config_entries.async_entries(DOMAIN)
    }


class IammeterConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Iammeter."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.host = None
        self.api = None

    async def _test_connection(self, host, port):
        with async_timeout.timeout(PLATFORM_TIMEOUT):
            try:
                self.api = await iammeter.real_time_api(host, port)
            except (IamMeterError, asyncio.TimeoutError):
                return False
        return True

    async def async_step_user(self, user_input=None):
        """Step when user initializes a integration."""
        errors = {}
        if user_input is not None:
            # set some defaults in case we need to return to the form
            name = user_input.get(CONF_NAME, DEFAULT_NAME)
            port = user_input.get(CONF_PORT, DEFAULT_PORT)
            host_entry = user_input.get(CONF_HOST)
            url = urlparse(host_entry, "http")
            netloc = url.netloc or url.path
            path = url.path if url.netloc else ""
            url = ParseResult("http", netloc, path, *url[3:])
            host = netloc

            connect_ok = False
            connect_ok = await self._test_connection(host, port)
            if not connect_ok:
                errors[CONF_NAME] = "cannot_connect"
            else:
                if self.api:
                    dev_sn = self.api.iammeter.serial_number
                    await self.async_set_unique_id(dev_sn)
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=name,
                        data={
                            CONF_NAME: dev_sn,
                            CONF_HOST: host,
                            CONF_PORT: port,
                        },
                    )

        else:
            user_input = {}
            user_input[CONF_NAME] = DEFAULT_NAME
            user_input[CONF_PORT] = DEFAULT_PORT
            user_input[CONF_HOST] = DEFAULT_HOST

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
                    vol.Required(
                        CONF_HOST, default=user_input.get(CONF_HOST, DEFAULT_HOST)
                    ): str,
                    vol.Required(
                        CONF_PORT, default=user_input.get(CONF_PORT, DEFAULT_PORT)
                    ): str,
                }
            ),
            errors=errors,
        )

    async def async_step_import(self, user_input=None):
        """Import a config entry."""
        host_entry = user_input.get(CONF_HOST, DEFAULT_HOST)
        name = user_input.get(CONF_NAME, DEFAULT_NAME)
        port = user_input.get(CONF_PORT, DEFAULT_PORT)

        url = urlparse(host_entry, "http")
        netloc = url.netloc or url.path
        path = url.path if url.netloc else ""
        url = ParseResult("http", netloc, path, *url[3:])
        host = url.geturl()
        user_input[CONF_NAME] = name
        user_input[CONF_PORT] = port
        user_input[CONF_HOST] = host

        connect_ok = False
        connect_ok = await self._test_connection(host, port)
        if connect_ok and self.api:
            await self.async_set_unique_id(self.api.iammeter.serial_number)
            self._abort_if_unique_id_configured()
        return await self.async_step_user(user_input)
