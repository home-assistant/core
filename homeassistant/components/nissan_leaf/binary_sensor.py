"""Plugged In Status Support for the Nissan Leaf."""
from __future__ import annotations

import logging

from pycarwings2.pycarwings2 import Leaf

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import LeafEntity
from .const import DATA_CHARGING, DATA_LEAF, DATA_PLUGGED_IN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up of a Nissan Leaf binary sensor from a config entry."""

    # FIXME: Should be making use of config_entry here I think
    entities: list[LeafEntity] = []
    for vin, datastore in hass.data[DATA_LEAF].items():
        _LOGGER.debug("Adding binary_sensors for vin=%s", vin)
        entities.append(LeafPluggedInSensor(datastore))
        entities.append(LeafChargingSensor(datastore))

    async_add_entities(entities, True)


class LeafPluggedInSensor(LeafEntity, BinarySensorEntity):
    """Plugged In Sensor class."""

    _attr_device_class = BinarySensorDeviceClass.PLUG
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, car: Leaf) -> None:
        """Set up plug status sensor."""
        super().__init__(car)
        self._attr_unique_id = f"{self.car.leaf.vin.lower()}_plugstatus"

    @property
    def name(self) -> str:
        """Sensor name."""
        return f"{self.car.leaf.nickname} Plug Status"

    @property
    def available(self) -> bool:
        """Sensor availability."""
        return self.car.data[DATA_PLUGGED_IN] is not None

    @property
    def is_on(self) -> bool:
        """Return true if plugged in."""
        return bool(self.car.data[DATA_PLUGGED_IN])


class LeafChargingSensor(LeafEntity, BinarySensorEntity):
    """Charging Sensor class."""

    _attr_device_class = BinarySensorDeviceClass.BATTERY_CHARGING
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, car: Leaf) -> None:
        """Set up charging status sensor."""
        super().__init__(car)
        self._attr_unique_id = f"{self.car.leaf.vin.lower()}_chargingstatus"

    @property
    def name(self) -> str:
        """Sensor name."""
        return f"{self.car.leaf.nickname} Charging Status"

    @property
    def available(self) -> bool:
        """Sensor availability."""
        return self.car.data[DATA_CHARGING] is not None

    @property
    def is_on(self) -> bool:
        """Return true if charging."""
        return bool(self.car.data[DATA_CHARGING])
