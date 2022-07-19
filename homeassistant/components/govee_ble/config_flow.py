"""Config flow for govee_ble integration."""
from __future__ import annotations

from typing import Any

from govee_ble import GoveeBluetoothDeviceData

from homeassistant.components.bluetooth import BluetoothServiceInfo
from homeassistant.config_entries import ConfigFlow
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN


class GoveeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for govee."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovery_info: BluetoothServiceInfo | None = None
        self._discovered_device: GoveeBluetoothDeviceData | None = None

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfo
    ) -> FlowResult:
        """Handle the bluetooth discovery step."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        device = GoveeBluetoothDeviceData()
        device.generate_update(discovery_info)
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
        device_name = device.get_device_name() or discovery_info.name
        if user_input is not None:
            return self.async_create_entry(title=device_name, data={})

        self._set_confirm_only()
        placeholders = {"name": device_name}
        self.context["title_placeholders"] = placeholders
        return self.async_show_form(
            step_id="bluetooth_confirm", description_placeholders=placeholders
        )

    # TODO: async_step_user to get the list of discovered devices
    # from bluetooth.async_get_devices()
