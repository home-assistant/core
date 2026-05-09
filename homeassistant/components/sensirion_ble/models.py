"""Models for the sensirion_ble integration."""

from homeassistant.components.bluetooth.passive_update_processor import (
    PassiveBluetoothProcessorCoordinator,
)
from homeassistant.config_entries import ConfigEntry

type SensirionBluetoothConfigEntry = ConfigEntry[PassiveBluetoothProcessorCoordinator]
