"""Config flow for Landis+Gyr Heat Meter integration."""

import asyncio
import logging
from typing import Any, override

import serialx
import ultraheat_api
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_DEVICE
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import SerialPortSelector

from .const import DOMAIN, ULTRAHEAT_TIMEOUT

_LOGGER = logging.getLogger(__name__)


STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_DEVICE): SerialPortSelector(),
    }
)


class LandisgyrConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ultraheat Heat Meter."""

    VERSION = 2

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step when setting up serial configuration."""
        errors = {}

        if user_input is not None:
            dev_path = user_input[CONF_DEVICE]
            _LOGGER.debug("Using this path : %s", dev_path)

            try:
                return await self.validate_and_create_entry(dev_path)
            except CannotConnect:
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def validate_and_create_entry(self, dev_path):
        """Try to connect to the device path and return an entry."""
        model, device_number = await self.validate_ultraheat(dev_path)

        _LOGGER.debug("Got model %s and device_number %s", model, device_number)
        await self.async_set_unique_id(f"{device_number}")
        self._abort_if_unique_id_configured()
        data = {
            CONF_DEVICE: dev_path,
            "model": model,
            "device_number": device_number,
        }
        return self.async_create_entry(
            title=model,
            data=data,
        )

    async def validate_ultraheat(self, port: str) -> tuple[str, str]:
        """Validate the user input allows us to connect."""

        reader = ultraheat_api.UltraheatReader(port)
        heat_meter = ultraheat_api.HeatMeterService(reader)
        try:
            async with asyncio.timeout(ULTRAHEAT_TIMEOUT):
                # validate and retrieve the model and device number for a unique id
                data = await self.hass.async_add_executor_job(heat_meter.read)

        except (OSError, TimeoutError, serialx.SerialException) as err:
            _LOGGER.warning("Failed read data from: %s. %s", port, err)
            raise CannotConnect(f"Error communicating with device: {err}") from err

        _LOGGER.debug("Successfully connected to %s. Got data: %s", port, data)
        return data.model, data.device_number


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
