"""Config flow for Anthem A/V Receivers integration."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import anthemav
from anthemav.connection import Connection
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_NAME, CONF_PORT
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import format_mac

from .const import (
    CONF_MODEL,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DOMAIN,
    EMPTY_MAC,
    UNKNOWN_MODEL,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


async def connect_device(user_input: dict[str, Any]) -> Connection:
    """Connect to the AVR device."""

    @callback
    def async_anthemav_update_callback(message):
        """Receive notification from transport that new data exists."""
        _LOGGER.debug("Received update callback from AVR: %s", message)
        if "IDN" in message:
            user_input[CONF_MAC] = None
        elif "IDM" in message:
            user_input[CONF_MODEL] = None
        if CONF_MAC in user_input and CONF_MODEL in user_input:
            deviceinfo_received.set()

    deviceinfo_received = asyncio.Event()
    avr = await anthemav.Connection.create(
        host=user_input[CONF_HOST],
        port=user_input[CONF_PORT],
        auto_reconnect=False,
        update_callback=async_anthemav_update_callback,
    )
    await avr.reconnect()
    await asyncio.wait_for(deviceinfo_received.wait(), 5)
    return avr


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
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
                "Can't established connection to %s:%s",
                user_input[CONF_HOST],
                user_input[CONF_PORT],
            )
            errors["base"] = "cannot_connect"
        except asyncio.TimeoutError:
            errors["base"] = "cannot_receive_deviceinfo"
        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.exception(err)
            errors["base"] = "unknown"
        else:
            user_input[CONF_MAC] = format_mac(avr.protocol.macaddress)
            user_input[CONF_MODEL] = avr.protocol.model
            if (
                user_input[CONF_MAC] == EMPTY_MAC
                or user_input[CONF_MODEL] == UNKNOWN_MODEL
            ):
                _LOGGER.error("Invalid MacAddress or model")
                errors["base"] = "cannot_receive_deviceinfo"
            else:
                await self.async_set_unique_id(user_input[CONF_MAC])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_NAME], data=user_input
                )
        finally:
            if avr is not None:
                avr.close()

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_import(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Import a config entry from configuration.yaml."""
        return await self.async_step_user(user_input)
