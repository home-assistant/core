"""Config flow for Roth Touchline floor heating controller."""
from __future__ import annotations

import logging
import re
from typing import Any

from pytouchline import PyTouchline
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
    }
)

RESULT_SUCCESS = "success"
RESULT_CANNOT_CONNECT = "cannot_connect"


def _try_connect_and_fetch_basic_info(host):
    """Attempt to connect and, if successful, fetch number of devices."""
    py_touchline = PyTouchline()
    result = {"type": None, "data": {}}
    number_of_devices = None
    try:
        number_of_devices = int(py_touchline.get_number_of_devices(host))
        if number_of_devices:
            result["type"] = RESULT_SUCCESS
            result["data"] = None

            _LOGGER.debug(
                "Number of devices found: %s",
                number_of_devices,
            )
            device = PyTouchline(id=0)
            device.update()
            controller_id = device.get_controller_id()
            result["data"] = controller_id
            return result
    except ConnectionRefusedError:
        _LOGGER.debug(
            "Failed to connect to device %s. Check the IP address "
            "as well as whether the device is connected to power and network",
            host,
        )
        result["type"] = RESULT_CANNOT_CONNECT
    return result


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Roth Touchline."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA)

        # Abort if an entry with same host and port is present.
        self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})

        errors = {}
        host = user_input[CONF_HOST]
        # Remove HTTPS and HTTP from URL
        pattern = "https?://"
        user_input[CONF_HOST] = re.sub(pattern, "", user_input[CONF_HOST])
        user_input[CONF_HOST] = "http://" + user_input[CONF_HOST]
        if not cv.url(user_input[CONF_HOST]):
            errors["base"] = "invalid_input"
        else:
            self._async_abort_entries_match({CONF_HOST: host})
            result = await self.hass.async_add_executor_job(
                _try_connect_and_fetch_basic_info, user_input[CONF_HOST]
            )

            if result["type"] != RESULT_SUCCESS:
                errors["base"] = "cannot_connect"

        if errors:
            return self.async_show_form(
                step_id="user", data_schema=DATA_SCHEMA, errors=errors
            )

        await self.async_set_unique_id(result["data"])
        self._abort_if_unique_id_configured()

        return self.async_create_entry(title=user_input[CONF_HOST], data=user_input)

    async def async_step_import(self, conf: dict[str, Any]) -> FlowResult:
        """Import a configuration from yaml configuration."""
        return await self.async_step_user(user_input=conf)
