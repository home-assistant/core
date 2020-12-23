"""Config flow for iammeter integration."""
import asyncio
import logging
from urllib.parse import ParseResult, urlparse

import async_timeout
from const import DEFAULT_HOST, DEFAULT_NAME, DEFAULT_PORT, DOMAIN
from iammeter import real_time_api
from iammeter.power_meter import IamMeterError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import ssdp
from homeassistant.components.ssdp import ATTR_SSDP_LOCATION
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import PlatformNotReady

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
        self._errors = {}
        self.discovered_conf = {}

    def _host_in_configuration_exists(self, host) -> bool:
        """Return True if host exists in configuration."""
        if host in iammeter_entries(self.hass):
            return True
        return False

    async def _test_connection(self, host, port):
        try:
            with async_timeout.timeout(PLATFORM_TIMEOUT):
                await real_time_api(host, port)
                return True
        except (IamMeterError, asyncio.TimeoutError) as err:
            _LOGGER.error("Device is not ready")
            raise PlatformNotReady from err
        return False

    async def async_step_user(self, user_input=None):
        """Step when user initializes a integration."""
        self._errors = {}
        if user_input is not None:
            # set some defaults in case we need to return to the form
            name = user_input.get(CONF_NAME)
            port = user_input.get(CONF_PORT, DEFAULT_PORT)
            host_entry = user_input.get(CONF_HOST)
            url = urlparse(host_entry, "http")
            netloc = url.netloc or url.path
            path = url.path if url.netloc else ""
            url = ParseResult("http", netloc, path, *url[3:])
            host = netloc

            if self._host_in_configuration_exists(name):
                self._errors[CONF_NAME] = "already_configured"
            else:
                if await self._test_connection(host, port):
                    return self.async_create_entry(
                        title=name,
                        data={CONF_NAME: name, CONF_HOST: host, CONF_PORT: port},
                    )
        else:
            user_input = {}
            user_input[CONF_NAME] = DEFAULT_NAME
            user_input[CONF_PORT] = DEFAULT_PORT
            user_input[CONF_HOST] = DEFAULT_HOST
            if self.discovered_conf:
                user_input.update(self.discovered_conf)

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
                    vol.Required(
                        CONF_PORT, default=user_input.get(CONF_PORT, DEFAULT_PORT)
                    ): str,
                }
            ),
            errors=self._errors,
        )

    async def async_step_ssdp(self, discovery_info):
        """Handle a discovered Heos device."""
        friendly_name = discovery_info[ssdp.ATTR_UPNP_FRIENDLY_NAME]
        host = urlparse(discovery_info[ATTR_SSDP_LOCATION]).hostname
        port = DEFAULT_PORT
        dev_sn = friendly_name[-8:]
        print(friendly_name, host)
        self.host = host
        self.discovered_conf = {
            CONF_NAME: friendly_name,
            CONF_HOST: host,
            CONF_PORT: port,
        }
        self.context.update({"title_placeholders": {"sn": dev_sn}})
        if self._host_in_configuration_exists(friendly_name):
            return self.async_abort(reason="already_configured")

        # unique_id should be serial for services purpose
        await self.async_set_unique_id(dev_sn, raise_on_progress=False)

        # Check if already configured
        self._abort_if_unique_id_configured()

        return await self.async_step_user()

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
