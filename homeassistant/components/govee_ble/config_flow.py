"""Config flow for govee_ble integration."""
from __future__ import annotations

from typing import Any

from homeassistant import config_entries
from homeassistant.components import bluetooth
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN
from .govee_parser import parse_govee_from_discovery_data


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for govee_ble."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovery_info: bluetooth.BluetoothServiceInfo | None = None
        self._discovered_device: dict[str, Any] | None = None

    async def async_step_bluetooth(
        self, discovery_info: bluetooth.BluetoothServiceInfo
    ) -> FlowResult:
        """Handle the bluetooth discovery step."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        if not (
            device := parse_govee_from_discovery_data(discovery_info.manufacturer_data)
        ):
            return self.async_abort(reason="not_govee")
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
        if user_input is not None:
            return self.async_create_entry(title=device["type"], data={})

        self._set_confirm_only()
        placeholders = {"model": device["type"], "address": discovery_info.address}
        self.context["title_placeholders"] = placeholders
        return self.async_show_form(
            step_id="bluetooth_confirm", description_placeholders=placeholders
        )
