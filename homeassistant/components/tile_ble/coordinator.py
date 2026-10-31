"""Coordinator for the Tile BLE integration."""

import logging

from homeassistant.components.bluetooth import BluetoothScanningMode
from homeassistant.components.bluetooth.passive_update_coordinator import (
    PassiveBluetoothDataUpdateCoordinator,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

type TileBleConfigEntry = ConfigEntry[TileBleCoordinator]


class TileBleCoordinator(PassiveBluetoothDataUpdateCoordinator):
    """Track the advertisements of a Tile."""

    def __init__(self, hass: HomeAssistant, address: str) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            address,
            BluetoothScanningMode.PASSIVE,
            connectable=False,
        )
