"""Binary Sensor platform for Advantage Air integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN as ADVANTAGE_AIR_DOMAIN
from .entity import AdvantageAirAcEntity, AdvantageAirZoneEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up AdvantageAir Binary Sensor platform."""

    instance = hass.data[ADVANTAGE_AIR_DOMAIN][config_entry.entry_id]

    entities: list[BinarySensorEntity] = []
    if aircons := instance["coordinator"].data.get("aircons"):
        for ac_key, ac_device in aircons.items():
            entities.append(AdvantageAirFilter(instance, ac_key))
            for zone_key, zone in ac_device["zones"].items():
                # Only add motion sensor when motion is enabled
                if zone["motionConfig"] >= 2:
                    entities.append(AdvantageAirZoneMotion(instance, ac_key, zone_key))
                # Only add MyZone if it is available
                if zone["type"] != 0:
                    entities.append(AdvantageAirZoneMyZone(instance, ac_key, zone_key))
    async_add_entities(entities)


class AdvantageAirFilter(AdvantageAirAcEntity, BinarySensorEntity):
    """Advantage Air Filter sensor."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_name = "Filter"

    def __init__(self, instance: dict[str, Any], ac_key: str) -> None:
        """Initialize an Advantage Air Filter sensor."""
        super().__init__(instance, ac_key)
        self._attr_unique_id += "-filter"

    @property
    def is_on(self) -> bool:
        """Return if filter needs cleaning."""
        return self._ac["filterCleanStatus"]


class AdvantageAirZoneMotion(AdvantageAirZoneEntity, BinarySensorEntity):
    """Advantage Air Zone Motion sensor."""

    _attr_device_class = BinarySensorDeviceClass.MOTION

    def __init__(self, instance: dict[str, Any], ac_key: str, zone_key: str) -> None:
        """Initialize an Advantage Air Zone Motion sensor."""
        super().__init__(instance, ac_key, zone_key)
        self._attr_name = f'{self._zone["name"]} motion'
        self._attr_unique_id += "-motion"

    @property
    def is_on(self) -> bool:
        """Return if motion is detect."""
        return self._zone["motion"] == 20


class AdvantageAirZoneMyZone(AdvantageAirZoneEntity, BinarySensorEntity):
    """Advantage Air Zone MyZone sensor."""

    _attr_entity_registry_enabled_default = False
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, instance: dict[str, Any], ac_key: str, zone_key: str) -> None:
        """Initialize an Advantage Air Zone MyZone sensor."""
        super().__init__(instance, ac_key, zone_key)
        self._attr_name = f'{self._zone["name"]} myZone'
        self._attr_unique_id += "-myzone"

    @property
    def is_on(self) -> bool:
        """Return if this zone is the myZone."""
        return self._zone["number"] == self._ac["myZone"]
