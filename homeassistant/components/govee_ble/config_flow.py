"""Config flow for govee_ble integration."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, cast

from govee_ble import GoveeBluetoothDeviceData
import voluptuous as vol

from homeassistant.components.bluetooth import (
    BluetoothCallbackMatcher,
    BluetoothChange,
    BluetoothServiceInfo,
    async_register_callback,
)
from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import CALLBACK_TYPE, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.loader import async_get_integration

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
DISCOVERY_TIMEOUT = 10
DeviceData = GoveeBluetoothDeviceData


class GoveeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for govee."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovery_info: BluetoothServiceInfo | None = None
        self._discovered_device: DeviceData | None = None
        self._discovered_devices: dict[str, str] = {}

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfo
    ) -> FlowResult:
        """Handle the bluetooth discovery step."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        device = DeviceData()
        if not device.supported(discovery_info):
            return self.async_abort(reason="not_supported")
        self._discovery_info = discovery_info
        self._discovered_device = device
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm discovery."""
        assert self._discovered_device is not None
        device = self._discovered_device
        assert self._discovery_info is not None
        discovery_info = self._discovery_info
        title = device.title or device.get_device_name() or discovery_info.name
        if user_input is not None:
            return self.async_create_entry(title=title, data={})

        self._set_confirm_only()
        placeholders = {"name": title}
        self.context["title_placeholders"] = placeholders
        return self.async_show_form(
            step_id="bluetooth_confirm", description_placeholders=placeholders
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the user step to pick discovered device."""
        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            await self.async_set_unique_id(address, raise_on_progress=False)
            return self.async_create_entry(
                title=self._discovered_devices[address], data={}
            )

        current_addresses = self._async_current_ids()

        @callback
        def _async_discover_device(
            discovery_info: BluetoothServiceInfo, change: BluetoothChange
        ) -> None:
            """Handle a discovered device."""
            address = discovery_info.address
            if address in current_addresses or address in self._discovered_devices:
                return
            device = DeviceData()
            if device.supported(discovery_info):
                self._discovered_devices[address] = (
                    device.title or device.get_device_name() or discovery_info.name
                )

        integration = await async_get_integration(self.hass, DOMAIN)
        assert integration.bluetooth is not None
        cancels: list[CALLBACK_TYPE] = []
        for matcher in integration.bluetooth:
            cancels.append(
                async_register_callback(
                    self.hass,
                    _async_discover_device,
                    cast(BluetoothCallbackMatcher, matcher),
                )
            )
        await asyncio.sleep(DISCOVERY_TIMEOUT)
        for cancel in cancels:
            cancel()

        if not self._discovered_devices:
            return self.async_abort(reason="no_devices_found")

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_ADDRESS): vol.In(self._discovered_devices)}
            ),
        )
