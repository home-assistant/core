"""Config flow for Vevor Heater integration."""
from __future__ import annotations

import logging
from typing import Any

from home_assistant_bluetooth import BluetoothServiceInfoBleak
from vevor_heater_ble.heater import VevorDevice
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import async_discovered_service_info
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("address"): str,
    }
)


async def validate_device(hass: HomeAssistant, address: str) -> dict[str, Any]:
    """Validate the given device."""
    ble_device = bluetooth.async_ble_device_from_address(hass, address)

    if not ble_device:
        raise CannotConnect()

    heater = VevorDevice(address=ble_device.address)
    await heater.refresh_status(ble_device)
    if not heater.status:
        raise CannotConnect()

    return {
        "title": "Vevor "
        + (str(ble_device.name) if ble_device.name else ble_device.address)
    }


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Vevor Heater."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovery_info: BluetoothServiceInfoBleak | None = None
        self._discovered_device: VevorDevice | None = None
        self._discovered_devices: dict[str, str] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the user step to pick discovered device."""
        if user_input is not None:
            address = user_input["address"]
            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=self._discovered_devices[address], data={}
            )

        current_addresses = self._async_current_ids()
        for discovery_info in async_discovered_service_info(self.hass, True):
            address = discovery_info.address
            if address in current_addresses or address in self._discovered_devices:
                continue

            try:
                await validate_device(self.hass, address)
                self._discovered_devices[address] = discovery_info.name
            except CannotConnect:
                return self.async_abort(reason="not_supported")

        if not self._discovered_devices:
            return self.async_abort(reason="no_devices_found")

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required("address"): vol.In(self._discovered_devices)}
            ),
        )

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> FlowResult:
        """Handle the bluetooth discovery step."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        try:
            await validate_device(self.hass, discovery_info.address)
        except CannotConnect:
            return self.async_abort(reason="not_supported")
        self._discovery_info = discovery_info
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm discovery."""
        assert self._discovery_info is not None
        discovery_info = self._discovery_info
        title = f"Vevor {discovery_info.name or discovery_info.address}"
        if user_input is not None:
            return self.async_create_entry(title=title, data={})

        self._set_confirm_only()
        return self.async_show_form(step_id="bluetooth_confirm")


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
