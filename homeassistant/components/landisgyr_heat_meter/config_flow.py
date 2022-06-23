"""Config flow for Landis+Gyr Heat Meter integration."""
from __future__ import annotations

import logging
import os

import async_timeout
import serial
import serial.tools.list_ports
from ultraheat_api import HeatMeterService, UltraheatReader
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_DEVICE
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

CONF_MANUAL_PATH = "Enter Manually"

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_DEVICE): str,
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ultraheat Heat Meter."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Step when setting up serial configuration."""
        errors = {}

        if user_input is not None:
            user_selection = user_input[CONF_DEVICE]
            if user_selection == CONF_MANUAL_PATH:
                return await self.async_step_setup_serial_manual_path()

            dev_path = await self.hass.async_add_executor_job(
                get_serial_by_id, user_selection
            )

            try:
                model, device_number = await self.validate_ultraheat(dev_path)
            except CannotConnect:
                errors["base"] = "cannot_connect"

            if not errors:
                await self.async_set_unique_id(device_number)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=model,
                    data=user_input | {"model": model, "device_number": device_number},
                )

        ports = await self.hass.async_add_executor_job(serial.tools.list_ports.comports)
        list_of_ports = {}
        for port in ports:
            list_of_ports[
                port.device
            ] = f"{port}, s/n: {port.serial_number or 'n/a'}" + (
                f" - {port.manufacturer}" if port.manufacturer else ""
            )
        list_of_ports[CONF_MANUAL_PATH] = CONF_MANUAL_PATH

        schema = vol.Schema({vol.Required(CONF_DEVICE): vol.In(list_of_ports)})
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_setup_serial_manual_path(self, user_input=None):
        """Set path manually."""
        errors = {}

        if user_input is not None:
            try:
                model, device_number = await self.validate_ultraheat(
                    user_input[CONF_DEVICE]
                )
            except CannotConnect:
                errors["base"] = "cannot_connect"

            if not errors:
                await self.async_set_unique_id(device_number)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=model,
                    data=user_input | {"model": model, "device_number": device_number},
                )

        schema = vol.Schema({vol.Required(CONF_DEVICE): str})
        return self.async_show_form(
            step_id="setup_serial_manual_path",
            data_schema=schema,
            errors=errors,
        )

    async def validate_ultraheat(self, port: str):
        """Validate the user input allows us to connect."""

        reader = UltraheatReader(port)
        heat_meter = HeatMeterService(reader)
        try:
            async with async_timeout.timeout(10):
                # validate and retrieve the model and device number for a unique id
                data = await self.hass.async_add_executor_job(heat_meter.read)
                _LOGGER.debug("Got data from Ultraheat API: %s", data)

        except Exception as err:
            _LOGGER.warning("Failed read data from: %s. %s", port, err)
            raise CannotConnect(f"Error communicating with device: {err}") from err

        _LOGGER.info("Successfully connected to %s", port)
        return data.model, data.device_number


def get_serial_by_id(dev_path: str) -> str:
    """Return a /dev/serial/by-id match for given device if available."""
    by_id = "/dev/serial/by-id"
    if not os.path.isdir(by_id):
        return dev_path

    for path in (entry.path for entry in os.scandir(by_id) if entry.is_symlink()):
        if os.path.realpath(path) == dev_path:
            return path
    return dev_path


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
