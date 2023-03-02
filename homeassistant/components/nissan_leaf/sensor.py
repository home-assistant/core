"""Battery Charge and Range Support for the Nissan Leaf."""
from __future__ import annotations

import logging

from voluptuous.validators import Number

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import PERCENTAGE, UnitOfLength
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.icon import icon_for_battery_level
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util.unit_conversion import DistanceConverter
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

from . import LeafDataStore, LeafEntity
from .const import (
    DATA_BATTERY,
    DATA_CHARGING,
    DATA_LEAF,
    DATA_RANGE_AC,
    DATA_RANGE_AC_OFF,
)

_LOGGER = logging.getLogger(__name__)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Sensors setup."""
    if discovery_info is None:
        return

    entities: list[LeafEntity] = []
    for vin, datastore in hass.data[DATA_LEAF].items():
        _LOGGER.debug("Adding sensors for vin=%s", vin)
        entities.append(LeafBatterySensor(datastore))
        entities.append(LeafRangeSensor(datastore, True))
        entities.append(LeafRangeSensor(datastore, False))

    add_entities(entities, True)


class LeafBatterySensor(LeafEntity, SensorEntity):
    """Nissan Leaf Battery Sensor."""

    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(self, car: LeafDataStore) -> None:
        """Set up battery sensor."""
        super().__init__(car)
        self._attr_unique_id = f"{self.car.leaf.vin.lower()}_soc"

    @property
    def name(self) -> str:
        """Sensor Name."""
        return f"{self.car.leaf.nickname} Charge"

    @property
    def native_value(self) -> Number | None:
        """Battery state percentage."""
        if self.car.data[DATA_BATTERY] is None:
            return None
        return round(self.car.data[DATA_BATTERY])

    @property
    def icon(self) -> str:
        """Battery state icon handling."""
        chargestate = self.car.data[DATA_CHARGING]
        return icon_for_battery_level(battery_level=self.state, charging=chargestate)


class LeafRangeSensor(LeafEntity, SensorEntity):
    """Nissan Leaf Range Sensor."""

    _attr_icon = "mdi:speedometer"

    def __init__(self, car: LeafDataStore, ac_on: bool) -> None:
        """Set up range sensor. Store if AC on."""
        self._ac_on = ac_on
        super().__init__(car)
        if ac_on:
            self._attr_unique_id = f"{self.car.leaf.vin.lower()}_range_ac"
        else:
            self._attr_unique_id = f"{self.car.leaf.vin.lower()}_range"

    @property
    def name(self) -> str:
        """Update sensor name depending on AC."""
        if self._ac_on is True:
            return f"{self.car.leaf.nickname} Range (AC)"
        return f"{self.car.leaf.nickname} Range"

    def log_registration(self) -> None:
        """Log registration."""
        _LOGGER.debug(
            "Registered LeafRangeSensor integration with Home Assistant for VIN %s",
            self.car.leaf.vin,
        )

    @property
    def native_value(self) -> float | None:
        """Battery range in miles or kms."""
        ret: float | None
        if self._ac_on:
            ret = self.car.data[DATA_RANGE_AC]
        else:
            ret = self.car.data[DATA_RANGE_AC_OFF]

        if ret is None:
            return None

        if self.car.hass.config.units is US_CUSTOMARY_SYSTEM or self.car.force_miles:
            ret = DistanceConverter.convert(
                ret, UnitOfLength.KILOMETERS, UnitOfLength.MILES
            )

        return round(ret)

    @property
    def native_unit_of_measurement(self) -> str:
        """Battery range unit."""
        if self.car.hass.config.units is US_CUSTOMARY_SYSTEM or self.car.force_miles:
            return UnitOfLength.MILES
        return UnitOfLength.KILOMETERS
