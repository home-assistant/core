"""Support for Wireless Sensor Tags."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.const import (
    ATTR_BATTERY_LEVEL,
    ATTR_VOLTAGE,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    UnitOfElectricPotential,
)
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Strength of signal in dBm
ATTR_TAG_SIGNAL_STRENGTH = "signal_strength"
# Indicates if tag is out of range or not
ATTR_TAG_OUT_OF_RANGE = "out_of_range"
# Number in percents from max power of tag receiver
ATTR_TAG_POWER_CONSUMPTION = "power_consumption"


class WirelessTagEntity(Entity):
    """Base class for HA implementation for Wireless Sensor Tag."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, tag, tag_id: str) -> None:
        """Initialize a base sensor for Wireless Sensor Tag platform."""
        self.coordinator = coordinator
        self._tag = tag
        self._tag_id = tag_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, tag.uuid)},
            name=tag.name,
            manufacturer="Wireless Sensor Tag",
            model="Wireless Sensor Tag",
            sw_version=getattr(tag, "version", None),
            serial_number=tag.uuid,
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            self.coordinator.last_update_success
            and self._tag_id in self.coordinator.data
            and self.coordinator.data[self._tag_id].is_alive
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        if self._tag_id not in self.coordinator.data:
            return {}

        tag = self.coordinator.data[self._tag_id]
        return {
            ATTR_BATTERY_LEVEL: int(tag.battery_remaining * 100),
            ATTR_VOLTAGE: (f"{tag.battery_volts:.2f}{UnitOfElectricPotential.VOLT}"),
            ATTR_TAG_SIGNAL_STRENGTH: (
                f"{tag.signal_strength}{SIGNAL_STRENGTH_DECIBELS_MILLIWATT}"
            ),
            ATTR_TAG_OUT_OF_RANGE: not tag.is_in_range,
            ATTR_TAG_POWER_CONSUMPTION: (f"{tag.power_consumption:.2f}{PERCENTAGE}"),
        }
