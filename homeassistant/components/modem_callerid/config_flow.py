"""Config flow for Modem Caller ID integration."""
from __future__ import annotations

import logging
import os
from typing import Any

from phone_modem import DEFAULT_PORT, PhoneModem
import serial.tools.list_ports
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_DEVICE, CONF_NAME
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_MANUAL_PATH, DEFAULT_NAME, DOMAIN, EXCEPTIONS

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema({"name": str, "device": str})


class PhoneModemFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Phone Modem."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initiated by the user."""
        errors = {}
        ports = await self.hass.async_add_executor_job(serial.tools.list_ports.comports)
        list_of_ports = [
            f"{p}, s/n: {p.serial_number or 'n/a'}"
            + (f" - {p.manufacturer}" if p.manufacturer else "")
            for p in ports
        ]
        if not list_of_ports:
            return await self.async_step_user_manual()

        list_of_ports.append(CONF_MANUAL_PATH)

        if user_input is not None:
            user_selection = user_input[CONF_DEVICE]
            if user_selection == CONF_MANUAL_PATH:
                return await self.async_step_user_manual()
            port = ports[list_of_ports.index(user_selection)]
            dev_path = await self.hass.async_add_executor_job(
                get_serial_by_id, port.device
            )
            entry, errors = await self._async_step_common(
                user_input, dev_path, port.serial_number
            )
            if errors is None:
                return entry

        schema = vol.Schema({vol.Required(CONF_DEVICE): vol.In(list_of_ports)})
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_user_manual(self, user_input=None):
        """Handle a flow with manual device path."""
        errors = {}
        if user_input is not None:
            entry, errors = await self._async_step_common(
                user_input, user_input[CONF_DEVICE]
            )
            if errors is None:
                return entry

        user_input = user_input or {}
        return self.async_show_form(
            step_id="user_manual",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_DEVICE,
                        default=user_input.get(CONF_DEVICE) or DEFAULT_PORT,
                    ): str,
                }
            ),
            errors=errors,
        )

    async def async_step_import(self, config: dict[str, Any]) -> FlowResult:
        """Import a config entry from configuration.yaml."""
        if self._async_current_entries():
            _LOGGER.warning(
                "Loading Modem_callerid via platform setup is deprecated; Please remove it from your configuration"
            )
            return self.async_abort(reason="already_configured")
        if CONF_DEVICE not in config:
            config[CONF_DEVICE] = DEFAULT_PORT

        return await self.async_step_user_manual(config)

    async def _async_step_common(self, user_input, dev_path, ser_number=None):
        """Handle common flow step."""
        errors = {}
        await self.async_set_unique_id(ser_number)
        self._abort_if_unique_id_configured(updates={CONF_DEVICE: dev_path})
        try:
            api = PhoneModem()
            await api.test(dev_path)
            entry = self.async_create_entry(
                title=user_input.get(CONF_NAME, DEFAULT_NAME),
                data={CONF_DEVICE: dev_path},
            )
            return entry, None

        except EXCEPTIONS:
            errors["base"] = "cannot_connect"
            return None, errors


def get_serial_by_id(dev_path: str) -> str:
    """Return a /dev/serial/by-id match for given device if available."""
    by_id = "/dev/serial/by-id"
    if not os.path.isdir(by_id):
        return dev_path

    for path in (entry.path for entry in os.scandir(by_id) if entry.is_symlink()):
        if os.path.realpath(path) == dev_path:
            return path
    return dev_path
