"""Config flow for Antifurto365 iAlarmXR integration."""
from __future__ import annotations

import logging
from logging import Logger
from typing import Any

from pyialarmxr import (
    IAlarmXR,
    IAlarmXRGenericException,
    IAlarmXRSocketTimeoutException,
)
import voluptuous as vol

from homeassistant import config_entries, core
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN
from .utils import async_get_ialarmxr_mac

_LOGGER: Logger = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST, default=IAlarmXR.IALARM_P2P_DEFAULT_HOST): str,
        vol.Required(CONF_PORT, default=IAlarmXR.IALARM_P2P_DEFAULT_PORT): int,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


async def _async_get_device_formatted_mac(
    hass: core.HomeAssistant, username: str, password: str, host: str, port: int
) -> str:
    """Return iAlarmXR mac address."""

    ialarmxr = IAlarmXR(username, password, host, port)
    return await async_get_ialarmxr_mac(hass, ialarmxr)


class IAlarmConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Antifurto365 iAlarmXR."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""

        errors = {}

        if user_input is not None:
            mac = None
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]
            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]

            try:
                # If we are able to get the MAC address, we are able to establish
                # a connection to the device.
                mac = await _async_get_device_formatted_mac(
                    self.hass, username, password, host, port
                )
            except ConnectionError:
                errors["base"] = "cannot_connect"
            except IAlarmXRGenericException as ialarmxr_exception:
                _LOGGER.debug(
                    "IAlarmXRGenericException with message: [ %s ]",
                    ialarmxr_exception.message,
                )
                errors["base"] = "cannot_connect"
            except IAlarmXRSocketTimeoutException as ialarmxr_socket_timeout_exception:
                _LOGGER.debug(
                    "IAlarmXRSocketTimeoutException with message: [ %s ]",
                    ialarmxr_socket_timeout_exception.message,
                )
                errors["base"] = "timeout"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

            if not errors:
                await self.async_set_unique_id(mac)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_HOST], data=user_input
                )
        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )
