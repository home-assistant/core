"""Binary Sensor platform for Advantage Air integration."""

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_MOTION,
    DEVICE_CLASS_PROBLEM,
    BinarySensorEntity,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up AdvantageAir motion platform."""

    instance = hass.data[DOMAIN][config_entry.entry_id]

    if "aircons" in instance["coordinator"].data:
        entities = []
        for ac_key, ac_device in instance["coordinator"].data["aircons"].items():
            entities.append(AdvantageAirZoneFilter(instance, ac_key))
            for zone_key, zone in ac_device["zones"].items():
                # Only add motion sensor when motion is enabled
                if zone["motionConfig"] == 2:
                    entities.append(AdvantageAirZoneMotion(instance, ac_key, zone_key))
        async_add_entities(entities)


class AdvantageAirBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Parent class for Binary Sensor entities."""

    def __init__(self, instance, ac_key, zone_key=None):
        """Initialize common aspects of an Advantage Air sensor."""
        super().__init__(instance["coordinator"])
        self.async_change = instance["async_change"]
        self.ac_key = ac_key
        self.zone_key = zone_key

    @property
    def _ac(self):
        return self.coordinator.data["aircons"][self.ac_key]["info"]

    @property
    def _zone(self):
        if self.zone_key:
            return self.coordinator.data["aircons"][self.ac_key]["zones"][self.zone_key]
        return None

    @property
    def device_info(self):
        """Return parent device information."""
        return {
            "identifiers": {(DOMAIN, self.coordinator.data["system"]["rid"])},
            "name": self.coordinator.data["system"]["name"],
            "manufacturer": "Advantage Air",
            "model": self.coordinator.data["system"]["sysType"],
            "sw_version": self.coordinator.data["system"]["myAppRev"],
        }


class AdvantageAirZoneFilter(AdvantageAirBinarySensor):
    """AdvantageAir Filter."""

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


class AdvantageAirZoneMotion(AdvantageAirBinarySensor):
    """AdvantageAir Zone Motion."""

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

    @property
    def device_state_attributes(self):
        """Return additional motion configuration."""
        return {"motionConfig": self._zone["motionConfig"]}
