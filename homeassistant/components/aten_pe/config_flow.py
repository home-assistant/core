"""Config flow for aten_pe integration."""

import logging
from typing import Any, cast

from atenpdu import AtenPEError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
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
from .util import create_aten_pe_device

_LOGGER = logging.getLogger(__name__)


class AtenPEConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for aten_pe."""

    VERSION = 1

    async def _test_connection(
        self, host: str, port: str, config: dict[str, Any]
    ) -> bool:
        """Check if we can connect to the device."""
        dev = await self.hass.async_add_executor_job(
            create_aten_pe_device,
            host,
            port,
            config.get(CONF_COMMUNITY, DEFAULT_COMMUNITY),
            config.get(CONF_USERNAME, DEFAULT_USERNAME),
            config.get(CONF_AUTH_KEY),
            config.get(CONF_PRIV_KEY),
        )

        try:
            await dev.initialize()
            await dev.deviceMAC()
        except AtenPEError:
            _LOGGER.error("Could not connect to device at %s:%s", host, port)
            return False

        return True

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step when user initializes a integration."""
        errors = {}
        if user_input is not None:
            host = cast(str, user_input[CONF_HOST])
            port = cast(str, user_input.get(CONF_PORT, DEFAULT_PORT))
            await self.async_set_unique_id(f"{host}:{port}")
            self._abort_if_unique_id_configured()
            if await self._test_connection(host, port, user_input):
                title = host if port == DEFAULT_PORT else f"{host}:{port}"
                return self.async_create_entry(title=title, data=user_input)
            errors[CONF_HOST] = "cannot_connect"
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
            errors=errors,
        )

    async def async_step_import(
        self, user_input: dict[str, Any] | None
    ) -> ConfigFlowResult:
        """Import a config entry."""
        return await self.async_step_user(user_input)
