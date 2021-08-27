"""EnaSolar solar inverter configuration."""
from __future__ import annotations

import logging
from typing import Any

import pyenasolar
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.util import dt as dt_util

from .const import (
    CONF_CAPABILITY,
    CONF_DC_STRINGS,
    CONF_HOST,
    CONF_MAX_OUTPUT,
    CONF_NAME,
    CONF_SUN_DOWN,
    CONF_SUN_UP,
    DEFAULT_HOST,
    DEFAULT_NAME,
    DEFAULT_SUN_DOWN,
    DEFAULT_SUN_UP,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


@callback
def enasolar_entries(hass: HomeAssistant):
    """Return the hosts already configured."""
    return {
        entry.data[CONF_HOST] for entry in hass.config_entries.async_entries(DOMAIN)
    }


class EnaSolarConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """User Configuration of EnaSolar Integration."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._errors: dict[str, str] = {}
        self._enasolar = None
        self._data: dict[str, Any] = {}

    def _host_in_configuration_exists(self, host) -> bool:
        """Return True if host exists in configuration."""
        if host in enasolar_entries(self.hass):
            return True
        return False

    def _get_serial_no(self):
        return self._enasolar.get_serial_no()

    def _get_max_output(self):
        return self._enasolar.get_max_output()

    def _get_dc_strings(self):
        return self._enasolar.get_dc_strings()

    def _get_capability(self):
        return self._enasolar.get_capability()

    def _get_name(self):
        return self._data[CONF_NAME]

    async def _try_connect(self, host):
        kwargs = {}

        try:
            self._enasolar = pyenasolar.EnaSolar(host, **kwargs)
            await self._enasolar.interogate_inverter()
            return True

        except Exception as e:
            self._errors[CONF_HOST] = "cannot_connect"
            _LOGGER.error("Connection to EnaSolar inverter '%s' failed (%s)", host, e)
        return False

    async def async_step_user(self, user_input=None):
        """Step when user initializes a integration."""
        self._errors = {}

        if user_input is not None:
            input_valid = True
            if dt_util.parse_time(user_input[CONF_SUN_UP]) is None:
                self._errors[CONF_SUN_UP] = "time_invalid"
                input_valid = False
            if dt_util.parse_time(user_input[CONF_SUN_DOWN]) is None:
                self._errors[CONF_SUN_DOWN] = "time_invalid"
                input_valid = False
            if input_valid:
                if dt_util.parse_time(user_input[CONF_SUN_UP]) >= dt_util.parse_time(
                    user_input[CONF_SUN_DOWN]
                ):
                    self._errors[CONF_SUN_DOWN] = "time_range"
                    input_valid = False
            self._data[CONF_HOST] = user_input[CONF_HOST]
            if self._host_in_configuration_exists(self._data[CONF_HOST]):
                self._errors[CONF_HOST] = "already_configured"
                input_valid = False
            if input_valid:
                self._data[CONF_NAME] = user_input[CONF_NAME]
                self._data[CONF_SUN_UP] = user_input[CONF_SUN_UP]
                self._data[CONF_SUN_DOWN] = user_input[CONF_SUN_DOWN]
                if await self._try_connect(self._data[CONF_HOST]):
                    await self.async_set_unique_id(self._get_serial_no())
                    return await self.async_step_inverter()
        else:
            user_input = {}
            user_input[CONF_NAME] = DEFAULT_NAME
            user_input[CONF_HOST] = DEFAULT_HOST
            user_input[CONF_SUN_UP] = DEFAULT_SUN_UP
            user_input[CONF_SUN_DOWN] = DEFAULT_SUN_DOWN

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=user_input[CONF_HOST]): cv.string,
                    vol.Required(
                        CONF_SUN_UP, default=user_input[CONF_SUN_UP]
                    ): cv.string,
                    vol.Required(
                        CONF_SUN_DOWN, default=user_input[CONF_SUN_DOWN]
                    ): cv.string,
                    vol.Optional(CONF_NAME, default=user_input[CONF_NAME]): cv.string,
                }
            ),
            errors=self._errors,
            last_step=False,
        )

    async def async_step_inverter(self, user_input=None):
        """Give the user the opportunities to override inverter config."""

        self._errors = {}
        if user_input is not None:
            if not (
                (0 <= user_input[CONF_CAPABILITY] <= 7)
                or (256 <= user_input[CONF_CAPABILITY] <= 263)
            ):
                self._errors[CONF_CAPABILITY] = "capabilty_invalid"
            else:
                self._data[CONF_CAPABILITY] = user_input[CONF_CAPABILITY]
                self._data[CONF_MAX_OUTPUT] = user_input[CONF_MAX_OUTPUT]
                self._data[CONF_DC_STRINGS] = user_input[CONF_DC_STRINGS]
                title = self._get_name()
                return self.async_create_entry(title=title, data=self._data)
        else:
            user_input = {}
            user_input[CONF_MAX_OUTPUT] = self._get_max_output()
            user_input[CONF_DC_STRINGS] = self._get_dc_strings()
            user_input[CONF_CAPABILITY] = self._get_capability()

        return self.async_show_form(
            step_id="inverter",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_MAX_OUTPUT, default=user_input[CONF_MAX_OUTPUT]
                    ): vol.In([1.5, 2.0, 3.0, 3.8, 4.0, 5.0]),
                    vol.Required(
                        CONF_DC_STRINGS, default=user_input[CONF_DC_STRINGS]
                    ): vol.In([1, 2]),
                    vol.Required(
                        CONF_CAPABILITY, default=user_input[CONF_CAPABILITY]
                    ): int,
                }
            ),
            errors=self._errors,
            last_step=True,
        )

    async def async_step_import(self, user_input=None):
        """Import a config entry."""
        host = user_input[CONF_HOST]

        if self._host_in_configuration_exists(host):
            return self.async_abort(reason="already_configured")
        return await self.async_step_user(user_input)
