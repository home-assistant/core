"""Config flow for Rainforest RAVEn devices."""

from __future__ import annotations

import asyncio
from typing import Any

from aioraven.data import MeterType
from aioraven.device import RAVEnConnectionError
from aioraven.serial import RAVEnSerialDevice
import serial.tools.list_ports
from serial.tools.list_ports_common import ListPortInfo
import voluptuous as vol

from homeassistant.components import usb
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_DEVICE, CONF_MAC, CONF_NAME
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import DEFAULT_NAME, DOMAIN


def _format_id(value: str | int) -> str:
    if isinstance(value, str):
        return value
    return f"{value or 0:04X}"


def _generate_unique_id(info: ListPortInfo | usb.UsbServiceInfo) -> str:
    """Generate unique id from usb attributes."""
    return (
        f"{_format_id(info.vid)}:{_format_id(info.pid)}_{info.serial_number}"
        f"_{info.manufacturer}_{info.description}"
    )


class RainforestRavenConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Rainforest RAVEn devices."""

    def __init__(self) -> None:
        """Set up flow instance."""
        self._dev_path: str | None = None
        self._meter_macs: set[str] = set()

    async def _validate_device(self, dev_path: str) -> None:
        self._abort_if_unique_id_configured(updates={CONF_DEVICE: dev_path})
        async with (
            asyncio.timeout(5),
            RAVEnSerialDevice(dev_path) as raven_device,
        ):
            await raven_device.synchronize()
            meters = await raven_device.get_meter_list()
            if meters:
                for meter in meters.meter_mac_ids or ():
                    meter_info = await raven_device.get_meter_info(meter=meter)
                    if meter_info and (
                        meter_info.meter_type is None
                        or meter_info.meter_type == MeterType.ELECTRIC
                    ):
                        self._meter_macs.add(meter.hex())
        self._dev_path = dev_path

    async def async_step_meters(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Connect to device and discover meters."""
        errors: dict[str, str] = {}
        if user_input is not None:
            meter_macs = []
            for raw_mac in user_input.get(CONF_MAC, ()):
                mac = bytes.fromhex(raw_mac).hex()
                if mac not in meter_macs:
                    meter_macs.append(mac)
            if meter_macs and not errors:
                return self.async_create_entry(
                    title=user_input.get(CONF_NAME, DEFAULT_NAME),
                    data={
                        CONF_DEVICE: self._dev_path,
                        CONF_MAC: meter_macs,
                    },
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_MAC): SelectSelector(
                    SelectSelectorConfig(
                        options=sorted(self._meter_macs),
                        mode=SelectSelectorMode.DROPDOWN,
                        multiple=True,
                        translation_key=CONF_MAC,
                    )
                ),
            }
        )
        return self.async_show_form(step_id="meters", data_schema=schema, errors=errors)

    async def async_step_usb(
        self, discovery_info: usb.UsbServiceInfo
    ) -> ConfigFlowResult:
        """Handle USB Discovery."""
        device = discovery_info.device
        dev_path = await self.hass.async_add_executor_job(usb.get_serial_by_id, device)
        unique_id = _generate_unique_id(discovery_info)
        await self.async_set_unique_id(unique_id)
        try:
            await self._validate_device(dev_path)
        except TimeoutError:
            return self.async_abort(reason="timeout_connect")
        except RAVEnConnectionError:
            return self.async_abort(reason="cannot_connect")
        return await self.async_step_meters()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
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

        errors = {}
        if user_input is not None and user_input.get(CONF_DEVICE, "").strip():
            port = ports[unused_ports.index(str(user_input[CONF_DEVICE]))]
            dev_path = await self.hass.async_add_executor_job(
                usb.get_serial_by_id, port.device
            )
            unique_id = _generate_unique_id(port)
            await self.async_set_unique_id(unique_id)
            try:
                await self._validate_device(dev_path)
            except TimeoutError:
                errors[CONF_DEVICE] = "timeout_connect"
            except RAVEnConnectionError:
                errors[CONF_DEVICE] = "cannot_connect"
            else:
                return await self.async_step_meters()

        schema = vol.Schema({vol.Required(CONF_DEVICE): vol.In(unused_ports)})
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)
