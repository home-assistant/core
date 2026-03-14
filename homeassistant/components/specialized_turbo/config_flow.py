"""Config flow for Specialized Turbo integration."""

from __future__ import annotations

import logging
from typing import Any

from bleak import BleakClient
from bleak.exc import BleakError
from bleak_retry_connector import establish_connection
from specialized_turbo import is_specialized_advertisement
import voluptuous as vol

from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_ble_device_from_address,
    async_discovered_service_info,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS
from homeassistant.helpers.device_registry import format_mac

from .const import CONF_PIN, DOMAIN

_LOGGER = logging.getLogger(__name__)


class SpecializedTurboConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Specialized Turbo bikes."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovery_info: BluetoothServiceInfoBleak | None = None
        self._discovered_devices: dict[str, BluetoothServiceInfoBleak] = {}

    async def _async_test_connection(self, address: str) -> bool:
        """Attempt a BLE connection to verify the device is reachable."""
        ble_device = async_ble_device_from_address(self.hass, address, connectable=True)
        if ble_device is None:
            return False
        try:
            client = await establish_connection(BleakClient, ble_device, address)
            await client.disconnect()
        except BleakError, TimeoutError:
            return False
        return True

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle a Bluetooth discovery."""
        await self.async_set_unique_id(format_mac(discovery_info.address))
        self._abort_if_unique_id_configured()

        self._discovery_info = discovery_info
        self.context["title_placeholders"] = {
            "name": discovery_info.name or "Specialized Turbo",
            "address": discovery_info.address,
        }
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm Bluetooth discovery and collect PIN."""
        assert self._discovery_info is not None
        errors: dict[str, str] = {}

        if user_input is not None:
            if not await self._async_test_connection(self._discovery_info.address):
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=self._discovery_info.name or "Specialized Turbo",
                    data={
                        CONF_ADDRESS: self._discovery_info.address,
                        CONF_PIN: user_input.get(CONF_PIN),
                    },
                )

        return self.async_show_form(
            step_id="bluetooth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_PIN): vol.Coerce(int),
                }
            ),
            description_placeholders={
                "name": self._discovery_info.name or "Specialized Turbo",
                "address": self._discovery_info.address,
            },
            errors=errors,
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a user-initiated flow."""
        errors: dict[str, str] = {}

        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            await self.async_set_unique_id(format_mac(address), raise_on_progress=False)
            self._abort_if_unique_id_configured()

            if not await self._async_test_connection(address):
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=self._discovered_devices.get(address, address),
                    data={
                        CONF_ADDRESS: address,
                        CONF_PIN: user_input.get(CONF_PIN),
                    },
                )

        # Discover available Specialized bikes
        current_addresses = self._async_current_ids()
        for info in async_discovered_service_info(self.hass):
            if info.address in current_addresses:
                continue
            if _is_specialized_service_info(info):
                self._discovered_devices[info.address] = info

        if not self._discovered_devices:
            return self.async_abort(reason="no_devices_found")

        address_options = {
            addr: f"{info.name or 'Specialized Turbo'} ({addr})"
            for addr, info in self._discovered_devices.items()
        }

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ADDRESS): vol.In(address_options),
                    vol.Optional(CONF_PIN): vol.Coerce(int),
                }
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration to update the pairing PIN."""
        if user_input is not None:
            return self.async_update_reload_and_abort(
                self._get_reconfigure_entry(),
                data_updates={CONF_PIN: user_input.get(CONF_PIN)},
            )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_PIN): vol.Coerce(int),
                }
            ),
        )


def _is_specialized_service_info(info: BluetoothServiceInfoBleak) -> bool:
    """Check if a BluetoothServiceInfoBleak is a Specialized bike."""
    return bool(is_specialized_advertisement(info.manufacturer_data))
