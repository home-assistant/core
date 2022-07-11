"""Config flow for govee_ble integration."""
from __future__ import annotations

from homeassistant.components.bluetooth import BluetoothServiceInfo
from homeassistant.components.bluetooth.config_flow import BluetoothConfigFlow
from homeassistant.components.bluetooth.device import BluetoothDeviceData
from homeassistant.core import callback

from .const import DOMAIN
from .data import GoveeBluetoothDeviceData


class SensorPushBluetoothConfigFlow(BluetoothConfigFlow, domain=DOMAIN):
    """Handle a config flow for sensorpush."""

    @callback
    def async_device_data_class(
        self, discovery_info: BluetoothServiceInfo
    ) -> BluetoothDeviceData:
        """Return the device data class."""
        return GoveeBluetoothDeviceData()
