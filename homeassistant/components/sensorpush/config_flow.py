"""Config flow for sensorpush integration."""
from __future__ import annotations

from homeassistant.components.bluetooth.config_flow import BluetoothConfigFlow

from .const import DOMAIN
from .data import SensorPushBluetoothDeviceData


class GoveeBluetoothConfigFlow(BluetoothConfigFlow, domain=DOMAIN):
    """Handle a config flow for sensorpush."""

    DEVICE_DATA_CLASS = SensorPushBluetoothDeviceData
    USE_LOCAL_NAME = True
