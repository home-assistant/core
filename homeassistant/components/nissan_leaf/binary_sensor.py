"""Plugged In Status Support for the Nissan Leaf."""
from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import DATA_CHARGING, DATA_LEAF, DATA_PLUGGED_IN, LeafEntity

_LOGGER = logging.getLogger(__name__)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up of a Nissan Leaf binary sensor."""
    if discovery_info is None:
        return

    devices: list[LeafEntity] = []
    for vin, datastore in hass.data[DATA_LEAF].items():
        _LOGGER.debug("Adding binary_sensors for vin=%s", vin)
        devices.append(LeafPluggedInSensor(datastore))
        devices.append(LeafChargingSensor(datastore))

    add_entities(devices, True)


class LeafPluggedInSensor(LeafEntity, BinarySensorEntity):
    """Plugged In Sensor class."""

    _attr_device_class = BinarySensorDeviceClass.PLUG

    @property
    def name(self):
        """Sensor name."""
        return f"{self.car.leaf.nickname} Plug Status"

    @property
    def available(self):
        """Sensor availability."""
        return self.car.data[DATA_PLUGGED_IN] is not None

    @property
    def is_on(self):
        """Return true if plugged in."""
        return self.car.data[DATA_PLUGGED_IN]


class LeafChargingSensor(LeafEntity, BinarySensorEntity):
    """Charging Sensor class."""

    _attr_device_class = BinarySensorDeviceClass.BATTERY_CHARGING

    @property
    def name(self):
        """Sensor name."""
        return f"{self.car.leaf.nickname} Charging Status"

    @property
    def available(self):
        """Sensor availability."""
        return self.car.data[DATA_CHARGING] is not None

    @property
    def is_on(self):
        """Return true if charging."""
        return self.car.data[DATA_CHARGING]
