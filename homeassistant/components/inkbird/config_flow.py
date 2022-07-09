"""Config flow for inkbird integration."""
from __future__ import annotations

from homeassistant.components.bluetooth.config_flow import BluetoothConfigFlow

from .const import DOMAIN
from .data import INKBIRDBluetoothDeviceData


class GoveeBluetoothConfigFlow(BluetoothConfigFlow, domain=DOMAIN):
    """Handle a config flow for inkbird."""

    DEVICE_DATA_CLASS = INKBIRDBluetoothDeviceData
