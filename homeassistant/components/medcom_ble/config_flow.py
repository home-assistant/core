"""Config flow for Medcom BlE integration."""

from __future__ import annotations

import logging
from typing import Any

from bleak import BleakError
from bluetooth_data_tools import human_readable_name
from medcom_ble import MedcomBleDevice, MedcomBleDeviceData
from medcom_ble.const import INSPECTOR_SERVICE_UUID
import voluptuous as vol

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import (
    BluetoothServiceInfo,
    async_discovered_service_info,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS
from homeassistant.data_entry_flow import AbortFlow

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class InspectorBLEConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Medcom BLE radiation monitors."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovery_info: BluetoothServiceInfo | None = None
        self._discovered_devices: dict[str, BluetoothServiceInfo] = {}

    async def _get_device_data(
        self, service_info: BluetoothServiceInfo
    ) -> MedcomBleDevice:
        ble_device = bluetooth.async_ble_device_from_address(
            self.hass, service_info.address
        )
        if ble_device is None:
            _LOGGER.debug("no ble_device in _get_device_data")
            raise AbortFlow("cannot_connect")

        inspector = MedcomBleDeviceData(_LOGGER)

        return await inspector.update_device(ble_device)

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfo
    ) -> ConfigFlowResult:
        """Handle the bluetooth discovery step."""
        _LOGGER.debug("Discovered BLE device: %s", discovery_info.name)
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        self._discovery_info = discovery_info
        self.context["title_placeholders"] = {
            "name": human_readable_name(
                None, discovery_info.name, discovery_info.address
            )
        }

        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm discovery."""
        # We always will have self._discovery_info be a BluetoothServiceInfo at this point
        # and this helps mypy not complain
        assert self._discovery_info is not None

        if user_input is None:
            name = self._discovery_info.name or self._discovery_info.address
            return self.async_show_form(
                step_id="bluetooth_confirm",
                description_placeholders={"name": name},
            )

        return await self.async_step_check_connection()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user step to pick discovered device."""
        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            self._discovery_info = self._discovered_devices[address]
            return await self.async_step_check_connection()

        current_addresses = self._async_current_ids()
        for discovery_info in async_discovered_service_info(self.hass):
            address = discovery_info.address
            if address in current_addresses or address in self._discovered_devices:
                _LOGGER.debug(
                    "Detected a device that's already configured: %s", address
                )
                continue

            if INSPECTOR_SERVICE_UUID not in discovery_info.service_uuids:
                continue

            self._discovered_devices[discovery_info.address] = discovery_info

        if not self._discovered_devices:
            return self.async_abort(reason="no_devices_found")

        titles = {
            address: discovery.name
            for address, discovery in self._discovered_devices.items()
        }
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ADDRESS): vol.In(titles),
                },
            ),
        )

    async def async_step_check_connection(self) -> ConfigFlowResult:
        """Check we can connect to the device before considering the configuration is successful."""
        # We always will have self._discovery_info be a BluetoothServiceInfo at this point
        # and this helps mypy not complain
        assert self._discovery_info is not None

        _LOGGER.debug("Checking device connection: %s", self._discovery_info.name)
        try:
            await self._get_device_data(self._discovery_info)
        except BleakError:
            return self.async_abort(reason="cannot_connect")
        except AbortFlow:
            raise
        except Exception:
            _LOGGER.exception(
                "Error occurred reading information from %s",
                self._discovery_info.address,
            )
            return self.async_abort(reason="unknown")
        _LOGGER.debug("Device connection successful, proceeding")
        return self.async_create_entry(title=self._discovery_info.name, data={})
