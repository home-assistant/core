"""Binary Sensor platform for Advantage Air integration."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN as ADVANTAGE_AIR_DOMAIN
from .entity import AdvantageAirEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up AdvantageAir motion platform."""

    instance = hass.data[ADVANTAGE_AIR_DOMAIN][config_entry.entry_id]

    entities: list[BinarySensorEntity] = []
    for ac_key, ac_device in instance["coordinator"].data["aircons"].items():
        entities.append(AdvantageAirZoneFilter(instance, ac_key))
        for zone_key, zone in ac_device["zones"].items():
            # Only add motion sensor when motion is enabled
            if zone["motionConfig"] >= 2:
                entities.append(AdvantageAirZoneMotion(instance, ac_key, zone_key))
            # Only add MyZone if it is available
            if zone["type"] != 0:
                entities.append(AdvantageAirZoneMyZone(instance, ac_key, zone_key))
    async_add_entities(entities)


class AdvantageAirZoneFilter(AdvantageAirEntity, BinarySensorEntity):
    """Advantage Air Filter."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, instance, ac_key):
        """Initialize an Advantage Air Filter."""
        super().__init__(instance, ac_key)
        self._attr_name = f'{self._ac["name"]} Filter'
        self._attr_unique_id = (
            f'{self.coordinator.data["system"]["rid"]}-{ac_key}-filter'
        )

    @property
    def is_on(self):
        """Return if filter needs cleaning."""
        return self._ac["filterCleanStatus"]


class AdvantageAirZoneMotion(AdvantageAirEntity, BinarySensorEntity):
    """Advantage Air Zone Motion."""

    _attr_device_class = BinarySensorDeviceClass.MOTION

    def __init__(self, instance, ac_key, zone_key):
        """Initialize an Advantage Air Zone Motion."""
        super().__init__(instance, ac_key, zone_key)
        self._attr_name = f'{self._zone["name"]} Motion'
        self._attr_unique_id = (
            f'{self.coordinator.data["system"]["rid"]}-{ac_key}-{zone_key}-motion'
        )

    @property
    def is_on(self):
        """Return if motion is detect."""
        return self._zone["motion"] == 20


class AdvantageAirZoneMyZone(AdvantageAirEntity, BinarySensorEntity):
    """Advantage Air Zone MyZone."""

    _attr_entity_registry_enabled_default = False
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, instance, ac_key, zone_key):
        """Initialize an Advantage Air Zone MyZone."""
        super().__init__(instance, ac_key, zone_key)
        self._attr_name = f'{self._zone["name"]} MyZone'
        self._attr_unique_id = (
            f'{self.coordinator.data["system"]["rid"]}-{ac_key}-{zone_key}-myzone'
        )

    @property
    def is_on(self):
        """Return if this zone is the myZone."""
        return self._zone["number"] == self._ac["myZone"]
