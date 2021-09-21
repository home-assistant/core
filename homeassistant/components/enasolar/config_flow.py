"""EnaSolar solar inverter configuration."""
from __future__ import annotations

import logging
import socket
from typing import Any

import aiohttp
import pyenasolar
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.util import dt as dt_util

from .const import (
    CAPABILITY,
    CONF_CAPABILITY,
    CONF_DC_STRINGS,
    CONF_HOST,
    CONF_MAX_OUTPUT,
    CONF_NAME,
    CONF_SUN_DOWN,
    CONF_SUN_UP,
    DC_STRINGS,
    DEFAULT_HOST,
    DEFAULT_NAME,
    DEFAULT_SUN_DOWN,
    DEFAULT_SUN_UP,
    DOMAIN,
    MAX_OUTPUT,
)

_LOGGER = logging.getLogger(__name__)


def _get_ip(host):
    """Get the ip address from the host name."""
    try:
        return socket.gethostbyname(host)
    except socket.gaierror:
        return None


class EnaSolarConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """User Configuration of EnaSolar Integration."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        # Only exposes methods, no significant
        # code is executed during instantiation
        self._enasolar = pyenasolar.EnaSolar()
        self._data: dict[str, Any] = {}

    def _conf_for_inverter_exists(self, serial) -> bool:
        """Return True if inverter exists in configuration."""
        return any(
            entry
            for entry in self._async_current_entries(include_ignore=False)
            if serial == entry.unique_id
        )

    async def _try_connect(self, host):
        """Needed to mock connection when running tests."""
        await self._enasolar.interogate_inverter(host)

    def get_name(self):
        """Needed to mock name when running tests."""
        return self._data[CONF_NAME]

    def get_serial_no(self):
        """Needed to mock serial_no when running tests."""
        return self._enasolar.get_serial_no()

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get options flow for this handler."""
        return EnaSolarOptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input=None):
        """Step when user initializes a integration."""
        _errors = {}

        if user_input is not None:
            ip_address = await self.hass.async_add_executor_job(
                _get_ip, user_input[CONF_HOST]
            )
            if not ip_address:
                _errors[CONF_NAME] = "invalid_host"
            else:
                self._data[CONF_HOST] = user_input[CONF_HOST]
                self._data[CONF_NAME] = user_input[CONF_NAME]
                try:
                    await self._try_connect(self._data[CONF_HOST])
                    if self._conf_for_inverter_exists(self.get_serial_no()):
                        return self.async_abort(reason="already_configured")
                    await self.async_set_unique_id(self.get_serial_no())
                    return await self.async_step_inverter()
                except aiohttp.client_exceptions.ClientConnectorError:
                    _errors[CONF_HOST] = "cannot_connect"
                except aiohttp.client_exceptions.ClientResponseError:
                    _errors[CONF_HOST] = "unexpected_response"
                except Exception:  # pylint: disable=broad-except
                    _LOGGER.exception("Unexpected exception")
                    _errors["base"] = "unknown"
        else:
            user_input = {}
            user_input[CONF_NAME] = DEFAULT_NAME
            user_input[CONF_HOST] = DEFAULT_HOST

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=user_input[CONF_HOST]): cv.string,
                    vol.Optional(CONF_NAME, default=user_input[CONF_NAME]): cv.string,
                }
            ),
            errors=_errors,
            last_step=False,
        )

    async def async_step_inverter(self, user_input=None):
        """Give the user the opportunities to override inverter config."""

        _errors = {}
        if user_input is not None:
            # CAPABILITY is a 9 bit value, bits 1-3 and 9 representing
            # what features the Innverter has.
            if user_input[CONF_CAPABILITY] & ~CAPABILITY:
                _errors[CONF_CAPABILITY] = "capability_invalid"
            else:
                self._data.update(user_input)
                title = self.get_name()
                return self.async_create_entry(title=title, data=self._data)
        else:
            # Use the capability bits from the Inverter. This assumes it
            # had been possible to actually scrap them from the jScript
            user_input = {}
            user_input[CONF_MAX_OUTPUT] = self._enasolar.get_max_output()
            user_input[CONF_DC_STRINGS] = self._enasolar.get_dc_strings()
            user_input[CONF_CAPABILITY] = self._enasolar.get_capability()

        return self.async_show_form(
            step_id="inverter",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_MAX_OUTPUT, default=user_input[CONF_MAX_OUTPUT]
                    ): vol.In(MAX_OUTPUT),
                    vol.Required(
                        CONF_DC_STRINGS, default=user_input[CONF_DC_STRINGS]
                    ): vol.In(DC_STRINGS),
                    vol.Required(
                        CONF_CAPABILITY, default=user_input[CONF_CAPABILITY]
                    ): vol.Coerce(int),
                }
            ),
            errors=_errors,
            last_step=True,
        )


class EnaSolarOptionsFlowHandler(config_entries.OptionsFlow):
    """Allow Polling window to be updated."""

    def __init__(self, config_entry):
        """Initialize EnaSolar options flow."""
        self.config_entry = config_entry
        self._options = dict(config_entry.options)

    async def async_step_init(self, user_input=None):
        """Allow user to reset the Polling times."""

        _errors = {}
        if user_input is not None:
            input_valid = True
            if dt_util.parse_time(user_input[CONF_SUN_UP]) is None:
                _errors[CONF_SUN_UP] = "time_invalid"
                input_valid = False
            if dt_util.parse_time(user_input[CONF_SUN_DOWN]) is None:
                _errors[CONF_SUN_DOWN] = "time_invalid"
                input_valid = False
            if input_valid:
                if dt_util.parse_time(user_input[CONF_SUN_UP]) >= dt_util.parse_time(
                    user_input[CONF_SUN_DOWN]
                ):
                    _errors[CONF_SUN_DOWN] = "time_range"
                    input_valid = False
            if input_valid:
                self._options.update(user_input)
                return self.async_create_entry(title="", data=self._options)
        else:
            user_input = {}
            if self._options == {}:
                user_input[CONF_SUN_UP] = DEFAULT_SUN_UP
                user_input[CONF_SUN_DOWN] = DEFAULT_SUN_DOWN
            else:
                user_input.update(self._options)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SUN_UP, default=user_input[CONF_SUN_UP]
                    ): cv.string,
                    vol.Required(
                        CONF_SUN_DOWN, default=user_input[CONF_SUN_DOWN]
                    ): cv.string,
                }
            ),
            errors=_errors,
        )
