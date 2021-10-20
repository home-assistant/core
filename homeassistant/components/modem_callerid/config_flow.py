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


def _generate_unique_id(port: Any) -> str:
    """Generate unique id from usb attributes."""
    return f"{port.vid}:{port.pid}_{port.serial_number}_{port.manufacturer}_{port.description}"


class PhoneModemFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Phone Modem."""

    def __init__(self) -> None:
        """Set up flow instance."""
        self._device: str | None = None

    async def async_step_usb(self, discovery_info: dict[str, str]) -> FlowResult:
        """Handle USB Discovery."""
        device = discovery_info["device"]

        dev_path = await self.hass.async_add_executor_job(usb.get_serial_by_id, device)
        unique_id = f"{discovery_info['vid']}:{discovery_info['pid']}_{discovery_info['serial_number']}_{discovery_info['manufacturer']}_{discovery_info['description']}"
        if (
            await self.validate_device_errors(dev_path=dev_path, unique_id=unique_id)
            is None
        ):
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
        errors: dict[str, str] | None = {}
        if self._async_in_progress():
            return self.async_abort(reason="already_in_progress")
        ports = await self.hass.async_add_executor_job(serial.tools.list_ports.comports)
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
            errors = await self.validate_device_errors(
                dev_path=dev_path, unique_id=_generate_unique_id(port)
            )
            if errors is None:
                return self.async_create_entry(
                    title=user_input.get(CONF_NAME, DEFAULT_NAME),
                    data={CONF_DEVICE: dev_path},
                )
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
        ports = await self.hass.async_add_executor_job(serial.tools.list_ports.comports)
        for port in ports:
            if port.device == config[CONF_DEVICE]:
                if (
                    await self.validate_device_errors(
                        dev_path=port.device,
                        unique_id=_generate_unique_id(port),
                    )
                    is None
                ):
                    return self.async_create_entry(
                        title=config.get(CONF_NAME, DEFAULT_NAME),
                        data={CONF_DEVICE: port.device},
                    )
        return self.async_abort(reason="cannot_connect")

    async def validate_device_errors(
        self, dev_path: str, unique_id: str
    ) -> dict[str, str] | None:
        """Handle common flow input validation."""
        self._async_abort_entries_match({CONF_DEVICE: dev_path})
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured(updates={CONF_DEVICE: dev_path})
        try:
            api = PhoneModem()
            await api.test(dev_path)
        except EXCEPTIONS:
            return {"base": "cannot_connect"}
        else:
            return None
