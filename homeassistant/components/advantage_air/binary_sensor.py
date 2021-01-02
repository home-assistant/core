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
    async_add_entities(entities)


class AdvantageAirZoneFilter(AdvantageAirEntity, BinarySensorEntity):
    """Advantage Air Filter."""

    @property
    def name(self):
        """Return the name."""
        return f'{self._ac["name"]} Filter'

    @property
    def unique_id(self):
        """Return a unique id."""
        return f'{self.coordinator.data["system"]["rid"]}-{self.ac_key}-filter'

    @property
    def device_class(self):
        """Return the device class of the vent."""
        return DEVICE_CLASS_PROBLEM

    @property
    def is_on(self):
        """Return if filter needs cleaning."""
        return self._ac["filterCleanStatus"]


class AdvantageAirZoneMotion(AdvantageAirEntity, BinarySensorEntity):
    """Advantage Air Zone Motion."""

    @property
    def name(self):
        """Return the name."""
        return f'{self._zone["name"]} Motion'

    @property
    def unique_id(self):
        """Return a unique id."""
        return f'{self.coordinator.data["system"]["rid"]}-{self.ac_key}-{self.zone_key}-motion'

    @property
    def device_class(self):
        """Return the device class of the vent."""
        return DEVICE_CLASS_MOTION

    @property
    def is_on(self):
        """Return if motion is detect."""
        return self._zone["motion"]
