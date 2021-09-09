"""Config flow for Modem Caller ID integration."""
from __future__ import annotations

import logging
from typing import Any

from phone_modem import DEFAULT_PORT, PhoneModem
import serial.tools.list_ports
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import usb
from homeassistant.const import CONF_DEVICE, CONF_NAME
from homeassistant.data_entry_flow import FlowResult

from .const import DEFAULT_NAME, DOMAIN, EXCEPTIONS

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema({"name": str, "device": str})


def _generate_unique_id(port: Any):
    """Generate unique id from usb attributes."""
    return f"{port.vid}:{port.pid}_{port.serial_number}_{port.manufacturer}_{port.description}"


class PhoneModemFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Phone Modem."""

    def __init__(self) -> None:
        """Set up flow instance."""
        self._device: str | None = None

    async def async_step_usb(self, discovery_info: dict[str, str]) -> FlowResult:
        """Handle USB Discovery."""
        vid = discovery_info["vid"]
        pid = discovery_info["pid"]
        serial_number = discovery_info["serial_number"]
        device = discovery_info["device"]
        manufacturer = discovery_info["manufacturer"]
        description = discovery_info["description"]

        dev_path = await self.hass.async_add_executor_job(usb.get_serial_by_id, device)
        unique_id = f"{vid}:{pid}_{serial_number}_{manufacturer}_{description}"
        _, errors = await self.validate_input(dev_path=dev_path, unique_id=unique_id)
        if errors is None:
            self._device = dev_path
            return await self.async_step_usb_confirm()
        return self.async_abort(reason="cannot_connect")

    async def async_step_usb_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle USB Discovery confirmation."""
        if user_input is not None:
            return self.async_create_entry(
                title=user_input.get(CONF_NAME, DEFAULT_NAME),
                data={CONF_DEVICE: self._device},
            )
        self._set_confirm_only()
        return self.async_show_form(step_id="usb_confirm")

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initiated by the user."""
        if self._async_in_progress():
            return self.async_abort(reason="already_in_progress")
        errors = {}
        ports = await self.hass.async_add_executor_job(serial.tools.list_ports.comports)
        if self.source == config_entries.SOURCE_IMPORT and user_input is not None:
            for port in ports:
                if port.device == user_input[CONF_DEVICE]:
                    entry, errors = await self.validate_input(
                        user_input=user_input,
                        dev_path=port.device,
                        unique_id=_generate_unique_id(port),
                    )
                    if errors is None:
                        return entry
        existing_devices = [
            entry.data[CONF_DEVICE] for entry in self._async_current_entries()
        ]
        unused_ports = [
            usb.human_readable_device_name(
                port.device,
                port.serial_number,
                port.manufacturer,
                port.description,
                port.vid,
                port.pid,
            )
            for port in ports
            if port.device not in existing_devices
        ]
        if not unused_ports:
            return self.async_abort(reason="no_devices_found")

        if user_input is not None:
            port = ports[unused_ports.index(str(user_input.get(CONF_DEVICE)))]
            dev_path = await self.hass.async_add_executor_job(
                usb.get_serial_by_id, port.device
            )
            entry, errors = await self.validate_input(
                dev_path=dev_path, unique_id=_generate_unique_id(port)
            )
            if errors is None:
                return entry
        user_input = user_input or {}
        schema = vol.Schema({vol.Required(CONF_DEVICE): vol.In(unused_ports)})
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_import(self, config: dict[str, Any]) -> FlowResult:
        """Import a config entry from configuration.yaml."""
        if self._async_current_entries():
            _LOGGER.warning(
                "Loading Modem_callerid via platform setup is deprecated; Please remove it from your configuration"
            )
        if CONF_DEVICE not in config:
            config[CONF_DEVICE] = DEFAULT_PORT

        return await self.async_step_user(config)

    async def validate_input(self, user_input=None, dev_path=None, unique_id=None):
        """Handle common flow input validation."""
        user_input = user_input or {}
        errors = {}
        self._async_abort_entries_match({CONF_DEVICE: dev_path})
        await self.async_set_unique_id(unique_id)
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
