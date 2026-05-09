"""Models for the ThermoBeacon integration."""

from homeassistant.components.bluetooth.passive_update_processor import (
    PassiveBluetoothProcessorCoordinator,
)
from homeassistant.config_entries import ConfigEntry

type ThermoBeaconConfigEntry = ConfigEntry[PassiveBluetoothProcessorCoordinator]
