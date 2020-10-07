"""Support for Homekit motion sensors."""
import logging

from aiohomekit.model.characteristics import CharacteristicsTypes

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_GAS,
    DEVICE_CLASS_MOISTURE,
    DEVICE_CLASS_MOTION,
    DEVICE_CLASS_OCCUPANCY,
    DEVICE_CLASS_OPENING,
    DEVICE_CLASS_SMOKE,
    BinarySensorEntity,
)
from homeassistant.core import callback

from . import KNOWN_DEVICES, HomeKitEntity

_LOGGER = logging.getLogger(__name__)


class HomeKitMotionSensor(HomeKitEntity, BinarySensorEntity):
    """Representation of a Homekit motion sensor."""

    def get_characteristic_types(self):
        """Define the homekit characteristics the entity is tracking."""
        return [CharacteristicsTypes.MOTION_DETECTED]

    @property
    def device_class(self):
        """Define this binary_sensor as a motion sensor."""
        return DEVICE_CLASS_MOTION

    @property
    def is_on(self):
        """Has motion been detected."""
        return self.service.value(CharacteristicsTypes.MOTION_DETECTED)


class HomeKitContactSensor(HomeKitEntity, BinarySensorEntity):
    """Representation of a Homekit contact sensor."""

    def get_characteristic_types(self):
        """Define the homekit characteristics the entity is tracking."""
        return [CharacteristicsTypes.CONTACT_STATE]

    @property
    def device_class(self):
        """Define this binary_sensor as a opening sensor."""
        return DEVICE_CLASS_OPENING

    @property
    def is_on(self):
        """Return true if the binary sensor is on/open."""
        return self.service.value(CharacteristicsTypes.CONTACT_STATE) == 1


class HomeKitSmokeSensor(HomeKitEntity, BinarySensorEntity):
    """Representation of a Homekit smoke sensor."""

    @property
    def device_class(self) -> str:
        """Return the class of this sensor."""
        return DEVICE_CLASS_SMOKE

    def get_characteristic_types(self):
        """Define the homekit characteristics the entity is tracking."""
        return [CharacteristicsTypes.SMOKE_DETECTED]

    @property
    def is_on(self):
        """Return true if smoke is currently detected."""
        return self.service.value(CharacteristicsTypes.SMOKE_DETECTED) == 1


class HomeKitCarbonMonoxideSensor(HomeKitEntity, BinarySensorEntity):
    """Representation of a Homekit BO sensor."""

    @property
    def device_class(self) -> str:
        """Return the class of this sensor."""
        return DEVICE_CLASS_GAS

    def get_characteristic_types(self):
        """Define the homekit characteristics the entity is tracking."""
        return [CharacteristicsTypes.CARBON_MONOXIDE_DETECTED]

    @property
    def is_on(self):
        """Return true if CO is currently detected."""
        return self.service.value(CharacteristicsTypes.CARBON_MONOXIDE_DETECTED) == 1


class HomeKitOccupancySensor(HomeKitEntity, BinarySensorEntity):
    """Representation of a Homekit occupancy sensor."""

    @property
    def device_class(self) -> str:
        """Return the class of this sensor."""
        return DEVICE_CLASS_OCCUPANCY

    def get_characteristic_types(self):
        """Define the homekit characteristics the entity is tracking."""
        return [CharacteristicsTypes.OCCUPANCY_DETECTED]

    @property
    def is_on(self):
        """Return true if occupancy is currently detected."""
        return self.service.value(CharacteristicsTypes.OCCUPANCY_DETECTED) == 1


class HomeKitLeakSensor(HomeKitEntity, BinarySensorEntity):
    """Representation of a Homekit leak sensor."""

    def get_characteristic_types(self):
        """Define the homekit characteristics the entity is tracking."""
        return [CharacteristicsTypes.LEAK_DETECTED]

    @property
    def device_class(self):
        """Define this binary_sensor as a leak sensor."""
        return DEVICE_CLASS_MOISTURE

    @property
    def is_on(self):
        """Return true if a leak is detected from the binary sensor."""
        return self.service.value(CharacteristicsTypes.LEAK_DETECTED) == 1


ENTITY_TYPES = {
    "motion": HomeKitMotionSensor,
    "contact": HomeKitContactSensor,
    "smoke": HomeKitSmokeSensor,
    "carbon-monoxide": HomeKitCarbonMonoxideSensor,
    "occupancy": HomeKitOccupancySensor,
    "leak": HomeKitLeakSensor,
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Homekit lighting."""
    hkid = config_entry.data["AccessoryPairingID"]
    conn = hass.data[KNOWN_DEVICES][hkid]

    @callback
    def async_add_service(aid, service):
        entity_class = ENTITY_TYPES.get(service["stype"])
        if not entity_class:
            return False
        info = {"aid": aid, "iid": service["iid"]}
        async_add_entities([entity_class(conn, info)], True)
        return True

    conn.add_listener(async_add_service)
