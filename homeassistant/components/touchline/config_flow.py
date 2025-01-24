"""Config flow for Roth Touchline floor heating controller."""

from __future__ import annotations

import re

from pytouchline_extended import PyTouchline
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST
import homeassistant.helpers.config_validation as cv

from .const import _LOGGER, DOMAIN

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
    }
)

RESULT_SUCCESS = "success"
RESULT_CANNOT_CONNECT = "cannot_connect"


def _try_connect_and_fetch_basic_info(host):
    """Attempt to connect and, if successful, fetch number of devices."""
    py_touchline = PyTouchline(url=host)
    result = {"type": None, "data": None}
    number_of_devices = None
    device = PyTouchline(id=0, url=host)
    try:
        number_of_devices = int(py_touchline.get_number_of_devices())
        if number_of_devices:
            device.update()
            result["data"] = device.get_controller_id()
            if result["data"]:
                result["type"] = RESULT_SUCCESS
            return result
    except ConnectionRefusedError:
        _LOGGER.debug(
            "Failed to connect to device %s. Check the IP address "
            "as well as whether the device is connected to power and network",
            host,
        )
        result["type"] = RESULT_CANNOT_CONNECT
    except ConnectionError:
        _LOGGER.debug(
            "Failed to connect to device %s. Check the IP address "
            "as well as whether the device is connected to power and network",
            host,
        )
        result["type"] = RESULT_CANNOT_CONNECT
    _LOGGER.debug(
        "Number of devices found: %s",
        number_of_devices,
    )
    return result


class TouchlineConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Roth Touchline."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""

        errors = {}
        result: dict[str, str | None] = {"type": None, "data": None}

        if user_input is not None:
            # Abort if an entry with same host is present.
            self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})

            errors = self._validate_input(user_input)
            if errors:
                return self.async_show_form(
                    step_id="user", data_schema=DATA_SCHEMA, errors=errors
                )

            try:
                result = await self.hass.async_add_executor_job(
                    _try_connect_and_fetch_basic_info, user_input[CONF_HOST]
                )
            except ConnectionRefusedError as e:
                _LOGGER.error("Failed to connect: %s", e)
                errors["base"] = "cannot_connect"

            except ConnectionError as e:
                _LOGGER.error("Failed to connect: %s", e)
                errors["base"] = "cannot_connect"

            if result["type"] != RESULT_SUCCESS:
                errors["base"] = "cannot_connect"

            # Ensure `result["data"]` is not `None` before setting the unique ID
            if result["data"]:
                await self.async_set_unique_id(result["data"])
                self._abort_if_unique_id_configured()
            else:
                errors["base"] = "cannot_connect"

            _LOGGER.debug(
                "Host: %s",
                user_input[CONF_HOST],
            )
            if not errors:
                return self.async_create_entry(
                    title=user_input[CONF_HOST], data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_import(self, user_input: dict[str, str]) -> ConfigFlowResult:
        """Import a configuration from yaml configuration."""
        try:
            result = await self.hass.async_add_executor_job(
                _try_connect_and_fetch_basic_info, user_input[CONF_HOST]
            )
        except ConnectionRefusedError as e:
            _LOGGER.error("Failed to connect: %s", e)
            return self.async_abort(reason="cannot_connect")

        except ConnectionError as e:
            _LOGGER.error("Failed to connect: %s", e)
            return self.async_abort(reason="cannot_connect")

        if result["type"] != RESULT_SUCCESS or not result["data"]:
            return self.async_abort(reason="cannot_connect")

        return self.async_create_entry(title=user_input[CONF_HOST], data=user_input)

    def _validate_input(self, user_input: dict[str, str]) -> dict[str, str]:
        """Validate the user input."""
        errors = {}
        host = user_input[CONF_HOST]
        # Remove HTTPS and HTTP schema from URL.
        pattern = "https?://"
        host = re.sub(pattern, "", host)
        host = "http://" + host
        user_input[CONF_HOST] = host
        if not cv.url(host):
            errors["base"] = "invalid_input"
        else:
            self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})
        return errors
