"""Config flow for Anthem A/V Receivers integration."""
from __future__ import annotations

import logging
from typing import Any

import anthemav
from anthemav.connection import Connection
from anthemav.device_error import DeviceError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_MODEL, CONF_PORT
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import format_mac

from .const import DEFAULT_NAME, DEFAULT_PORT, DEVICE_TIMEOUT_SECONDS, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
    }
)


async def connect_device(user_input: dict[str, Any]) -> Connection:
    """Connect to the AVR device."""
    avr = await anthemav.Connection.create(
        host=user_input[CONF_HOST], port=user_input[CONF_PORT], auto_reconnect=False
    )
    await avr.reconnect()
    await avr.protocol.wait_for_device_initialised(DEVICE_TIMEOUT_SECONDS)
    return avr


class AnthemAVConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Anthem A/V Receivers."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}

        avr: Connection | None = None
        try:
            avr = await connect_device(user_input)
        except OSError:
            _LOGGER.error(
                "Couldn't establish connection to %s:%s",
                user_input[CONF_HOST],
                user_input[CONF_PORT],
            )
            errors["base"] = "cannot_connect"
        except DeviceError:
            _LOGGER.error(
                "Couldn't receive device information from %s:%s",
                user_input[CONF_HOST],
                user_input[CONF_PORT],
            )
            errors["base"] = "cannot_receive_deviceinfo"
        else:
            user_input[CONF_MAC] = format_mac(avr.protocol.macaddress)
            user_input[CONF_MODEL] = avr.protocol.model
            await self.async_set_unique_id(user_input[CONF_MAC])
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=DEFAULT_NAME, data=user_input)
        finally:
            if avr is not None:
                avr.close()

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
