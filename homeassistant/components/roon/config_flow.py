"""Config flow for roon integration."""

import asyncio
import logging

from roonapi import RoonApi, RoonDiscovery
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv

from .const import (
    AUTHENTICATE_TIMEOUT,
    CONF_ROON_ID,
    CONF_ROON_NAME,
    DEFAULT_NAME,
    DOMAIN,
    ROON_APPINFO,
)

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required("host"): cv.string,
        vol.Required("port", default=9330): cv.port,
    }
)

TIMEOUT = 120


class RoonHub:
    """Interact with roon during config flow."""

    def __init__(self, hass):
        """Initialise the RoonHub."""
        self._hass = hass

    async def discover(self):
        """Try and discover roon servers."""

        def get_discovered_servers(discovery):
            servers = discovery.all()
            discovery.stop()
            return servers

        discovery = RoonDiscovery(None)
        servers = await self._hass.async_add_executor_job(
            get_discovered_servers, discovery
        )
        _LOGGER.debug("Servers = %s", servers)
        return servers

    async def authenticate(self, host, port, servers):
        """Authenticate with one or more roon servers."""

        def stop_apis(apis):
            for api in apis:
                api.stop()

        token = None
        core_id = None
        core_name = None
        secs = 0
        if host is None:
            apis = [
                RoonApi(ROON_APPINFO, None, server[0], server[1], blocking_init=False)
                for server in servers
            ]
        else:
            apis = [RoonApi(ROON_APPINFO, None, host, port, blocking_init=False)]

        while secs <= TIMEOUT:
            # Roon can discover multiple devices - not all of which are proper servers, so try and authenticate with them all.
            # The user will only enable one - so look for a valid token
            auth_api = [api for api in apis if api.token is not None]

            secs += AUTHENTICATE_TIMEOUT
            if auth_api:
                core_id = auth_api[0].core_id
                core_name = auth_api[0].core_name
                token = auth_api[0].token
                break

            await asyncio.sleep(AUTHENTICATE_TIMEOUT)

        await self._hass.async_add_executor_job(stop_apis, apis)

        return (token, core_id, core_name)


async def discover(hass):
    """Connect and authenticate home assistant."""

    hub = RoonHub(hass)
    return await hub.discover()


async def authenticate(hass: HomeAssistant, host, port, servers):
    """Connect and authenticate home assistant."""

    hub = RoonHub(hass)
    (token, core_id, core_name) = await hub.authenticate(host, port, servers)
    if token is None:
        raise InvalidAuth

    return {
        CONF_HOST: host,
        CONF_PORT: port,
        CONF_ROON_ID: core_id,
        CONF_ROON_NAME: core_name,
        CONF_API_KEY: token,
    }


class RoonConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for roon."""

    VERSION = 1

    def __init__(self):
        """Initialize the Roon flow."""
        self._host = None
        self._port = None
        self._servers = []

    async def async_step_user(self, user_input=None):
        """Get roon core details via discovery."""

        self._servers = await discover(self.hass)

        # We discovered one or more  roon - so skip to authentication
        if self._servers:
            return await self.async_step_link()

        return await self.async_step_fallback()

    async def async_step_fallback(self, user_input=None):
        """Get host and port details from the user."""
        errors = {}

        if user_input is not None:
            self._host = user_input["host"]
            self._port = user_input["port"]
            return await self.async_step_link()

        return self.async_show_form(
            step_id="fallback", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_link(self, user_input=None):
        """Handle linking and authenticating with the roon server."""
        errors = {}
        if user_input is not None:
            # Do not authenticate if the host is already configured
            self._async_abort_entries_match({CONF_HOST: self._host})

            try:
                info = await authenticate(
                    self.hass, self._host, self._port, self._servers
                )

            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=DEFAULT_NAME, data=info)

        return self.async_show_form(step_id="link", errors=errors)


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
