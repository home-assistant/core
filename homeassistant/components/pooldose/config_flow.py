"""Config flow for the Seko Pooldose integration."""

from __future__ import annotations

import logging
import socket
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_SCAN_INTERVAL, CONF_TIMEOUT
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .const import CONF_SERIALNUMBER, DEFAULT_HOST, DEFAULT_SERIAL_NUMBER, DOMAIN

_LOGGER = logging.getLogger(__name__)

SCHEMA_DEVICE = vol.Schema(
    {
        vol.Required(CONF_HOST, default=DEFAULT_HOST): cv.string,
        vol.Required(CONF_SERIALNUMBER, default=DEFAULT_SERIAL_NUMBER): cv.string,
        vol.Optional(CONF_SCAN_INTERVAL): cv.positive_int,
        vol.Optional(CONF_TIMEOUT): cv.positive_int,
    }
)


class PooldoseConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Seko Pooldose."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            serial_number = user_input[CONF_SERIALNUMBER]

            await self.async_set_unique_id(serial_number)
            self._abort_if_unique_id_configured()

            # check if the host is reachable
            reachable = await self._async_check_host_reachable(user_input[CONF_HOST])

            if not reachable:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=f"Pooldose - S/N {serial_number}", data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=SCHEMA_DEVICE, errors=errors
        )

    async def _async_check_host_reachable(self, host: str) -> bool:
        """Async check if tcp port is reachable."""
        try:
            return await self.hass.async_add_executor_job(
                self._check_tcp_port, host, 80
            )
        except CannotConnect as e:
            _LOGGER.error("Can not connect to %s:%d – %s", host, 80, e)
            return False

    def _check_tcp_port(self, host: str, port: int) -> bool:
        try:
            with socket.create_connection((host, port), timeout=5):
                return True
        except (TimeoutError, OSError):
            return False


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
