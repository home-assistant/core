"""Binary Sensor platform for Advantage Air integration."""

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_MOTION,
    DEVICE_CLASS_PROBLEM,
    BinarySensorEntity,
)

from .const import DOMAIN as ADVANTAGE_AIR_DOMAIN
from .entity import AdvantageAirEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up AdvantageAir motion platform."""

    instance = hass.data[ADVANTAGE_AIR_DOMAIN][config_entry.entry_id]

    entities = []
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

    _attr_device_class = DEVICE_CLASS_PROBLEM

    def __init__(self):
        """Initialize an Advantage Air Filter."""
        super().__init__()
        self._attr_name = f'{self._ac["name"]} Filter'
        self._attr_unique_id = (
            f'{self.coordinator.data["system"]["rid"]}-{self.ac_key}-filter'
        )
        self._attr_is_on = self._ac["filterCleanStatus"]


class AdvantageAirZoneMotion(AdvantageAirEntity, BinarySensorEntity):
    """Advantage Air Zone Motion."""

    _attr_device_class = DEVICE_CLASS_MOTION

    def __init__(self):
        """Initialize an Advantage Air Zone Motion."""
        super().__init__()
        self._attr_name = f'{self._zone["name"]} Motion'
        self._attr_unique_id = f'{self.coordinator.data["system"]["rid"]}-{self.ac_key}-{self.zone_key}-motion'
        self._attr_is_on = self._zone["motion"]


class AdvantageAirZoneMyZone(AdvantageAirEntity, BinarySensorEntity):
    """Advantage Air Zone MyZone."""

    _attr_entity_registry_enabled_default = False

    def __init__(self):
        """Initialize an Advantage Air Zone MyZone."""
        super().__init__()
        self._attr_name = f'{self._zone["name"]} MyZone'
        self._attr_unique_id = f'{self.coordinator.data["system"]["rid"]}-{self.ac_key}-{self.zone_key}-myzone'
        self._attr_is_on = self._zone["number"] == self._ac["myZone"]
