"""Config flow for aten_pe integration."""
from __future__ import annotations

import logging

from atenpdu import AtenPE, AtenPEError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_USERNAME

from .const import (
    CONF_AUTH_KEY,
    CONF_COMMUNITY,
    CONF_PRIV_KEY,
    DEFAULT_COMMUNITY,
    DEFAULT_PORT,
    DEFAULT_USERNAME,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class AtenPEConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for aten_pe."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._errors: dict[str, str] = {}

    def _host_in_configuration_exists(self, host, port) -> bool:
        """Return True if host exists in configuration."""
        for entry in self.hass.config_entries.async_entries(DOMAIN):
            if entry.data.get(CONF_HOST) == host and entry.data.get(CONF_PORT) == port:
                return True
        return False

    async def _test_connection(self, host, port, config):
        """Check if we can connect to the device."""
        dev = AtenPE(
            node=host,
            serv=port,
            community=config.get(CONF_COMMUNITY, DEFAULT_COMMUNITY),
            username=config.get(CONF_USERNAME, DEFAULT_USERNAME),
            authkey=config.get(CONF_AUTH_KEY),
            privkey=config.get(CONF_PRIV_KEY),
        )

        try:
            await self.hass.async_add_executor_job(dev.initialize)
            await dev.deviceMAC()
            return True
        except AtenPEError:
            self._errors[CONF_HOST] = "cannot_connect"
            _LOGGER.error("Could not connect to device at %s:%s", host, port)
        return False

    async def async_step_user(self, user_input=None):
        """Step when user initializes a integration."""
        self._errors = {}
        if user_input is not None:
            host = user_input.get(CONF_HOST)
            port = user_input.get(CONF_PORT, DEFAULT_PORT)
            if self._host_in_configuration_exists(host, port):
                self._errors[CONF_HOST] = "already_configured"
            else:
                if await self._test_connection(host, port, user_input):
                    if port == DEFAULT_PORT:
                        title = host
                    else:
                        title = f"{host}:{port}"
                    return self.async_create_entry(title=title, data=user_input)
        else:
            user_input = {}

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=user_input.get(CONF_HOST)): str,
                    vol.Required(
                        CONF_PORT,
                        default=user_input.get(CONF_PORT, DEFAULT_PORT),
                    ): str,
                    vol.Optional(
                        CONF_COMMUNITY,
                        default=user_input.get(CONF_COMMUNITY, DEFAULT_COMMUNITY),
                    ): str,
                    vol.Optional(
                        CONF_USERNAME,
                        default=user_input.get(CONF_USERNAME, DEFAULT_USERNAME),
                    ): str,
                    vol.Optional(
                        CONF_AUTH_KEY,
                        default=user_input.get(CONF_AUTH_KEY, ""),
                    ): str,
                    vol.Optional(
                        CONF_PRIV_KEY,
                        default=user_input.get(CONF_PRIV_KEY, ""),
                    ): str,
                }
            ),
            errors=self._errors,
        )

    async def async_step_import(self, user_input=None):
        """Import a config entry."""
        host = user_input.get(CONF_HOST)
        port = user_input.get(CONF_PORT)
        if self._host_in_configuration_exists(host, port):
            return self.async_abort(reason="already_configured")
        return await self.async_step_user(user_input)
