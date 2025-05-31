"""Aeroflex adjustable bed entity implementation."""

from __future__ import annotations

import asyncio
import logging

from bleak.backends.device import BLEDevice

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import CONF_DEVICE_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)


class AeroflexBedEntity(Entity):
    """Base entity for Aeroflex bed."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, ble_device: BLEDevice
    ) -> None:
        """Initialize the bed entity."""
        self.hass = hass
        self.entry = entry
        self._ble_device = ble_device
        self._attr_has_entity_name = True

        # Get the device name from the config entry
        device_name = entry.data.get(
            CONF_DEVICE_NAME, f"Aeroflex Bed {ble_device.address}"
        )

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, ble_device.address)},
            name=device_name,
            manufacturer="Aeroflex",
            model="Adjustable Bed",
        )
        # Create a lock specific to this bed instance
        self._command_lock = asyncio.Lock()
