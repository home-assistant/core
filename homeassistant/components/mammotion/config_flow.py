"""Config flow for Mammotion Luba."""
from bleak import BLEDevice
from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import BluetoothServiceInfo
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS
from typing import Any
from .const import DOMAIN


class LubaConfigFlow(ConfigFlow, domain=DOMAIN):

    _address: str | None = None
    _discovered_devices: dict[str, BLEDevice] = {}

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfo
    ) -> ConfigFlowResult:
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()

        device = bluetooth.async_ble_device_from_address(
            self.hass, discovery_info.address
        )

        self._address = device.address
        self._discovered_devices = {device.address: device}

        self.context["title_placeholders"] = {"name": device.name}

        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm discovery."""
        assert self._address
        device = self._discovered_devices[self._address]

        if user_input is not None:
            return self.async_create_entry(title=device.name, data={
                CONF_ADDRESS: device.address,
            })

        self._set_confirm_only()
        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders=self.context["title_placeholders"],
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user step to pick discovered device."""
        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()

            device = self._discovered_devices[address]

            self.context["title_placeholders"] = {
                "name": device.name,
            }

            return self.async_create_entry(title=device.name, data={
                CONF_ADDRESS: device.address,
            })
