"""Support for Homekit motion sensors."""
from aiohomekit.model.characteristics import CharacteristicsTypes
from aiohomekit.model.services import ServicesTypes

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


class HomeKitMotionSensor(HomeKitEntity, BinarySensorEntity):
    """Representation of a Homekit motion sensor."""

    _attr_device_class = DEVICE_CLASS_MOTION

    def get_characteristic_types(self):
        """Define the homekit characteristics the entity is tracking."""
        return [CharacteristicsTypes.MOTION_DETECTED]

    @property
    def is_on(self):
        """Has motion been detected."""
        return self.service.value(CharacteristicsTypes.MOTION_DETECTED)


class HomeKitContactSensor(HomeKitEntity, BinarySensorEntity):
    """Representation of a Homekit contact sensor."""

    _attr_device_class = DEVICE_CLASS_OPENING

    def get_characteristic_types(self):
        """Define the homekit characteristics the entity is tracking."""
        return [CharacteristicsTypes.CONTACT_STATE]

    @property
    def is_on(self):
        """Return true if the binary sensor is on/open."""
        return self.service.value(CharacteristicsTypes.CONTACT_STATE) == 1


class HomeKitSmokeSensor(HomeKitEntity, BinarySensorEntity):
    """Representation of a Homekit smoke sensor."""

    _attr_device_class = DEVICE_CLASS_SMOKE

    def get_characteristic_types(self):
        """Define the homekit characteristics the entity is tracking."""
        return [CharacteristicsTypes.SMOKE_DETECTED]

    @property
    def is_on(self):
        """Return true if smoke is currently detected."""
        return self.service.value(CharacteristicsTypes.SMOKE_DETECTED) == 1


class HomeKitCarbonMonoxideSensor(HomeKitEntity, BinarySensorEntity):
    """Representation of a Homekit BO sensor."""

    _attr_device_class = DEVICE_CLASS_GAS

    def get_characteristic_types(self):
        """Define the homekit characteristics the entity is tracking."""
        return [CharacteristicsTypes.CARBON_MONOXIDE_DETECTED]

    @property
    def is_on(self):
        """Return true if CO is currently detected."""
        return self.service.value(CharacteristicsTypes.CARBON_MONOXIDE_DETECTED) == 1


class HomeKitOccupancySensor(HomeKitEntity, BinarySensorEntity):
    """Representation of a Homekit occupancy sensor."""

    _attr_device_class = DEVICE_CLASS_OCCUPANCY

    def get_characteristic_types(self):
        """Define the homekit characteristics the entity is tracking."""
        return [CharacteristicsTypes.OCCUPANCY_DETECTED]

    @property
    def is_on(self):
        """Return true if occupancy is currently detected."""
        return self.service.value(CharacteristicsTypes.OCCUPANCY_DETECTED) == 1


class HomeKitLeakSensor(HomeKitEntity, BinarySensorEntity):
    """Representation of a Homekit leak sensor."""

    _attr_device_class = DEVICE_CLASS_MOISTURE

    def get_characteristic_types(self):
        """Define the homekit characteristics the entity is tracking."""
        return [CharacteristicsTypes.LEAK_DETECTED]

    @property
    def is_on(self):
        """Return true if a leak is detected from the binary sensor."""
        return self.service.value(CharacteristicsTypes.LEAK_DETECTED) == 1


ENTITY_TYPES = {
    ServicesTypes.MOTION_SENSOR: HomeKitMotionSensor,
    ServicesTypes.CONTACT_SENSOR: HomeKitContactSensor,
    ServicesTypes.SMOKE_SENSOR: HomeKitSmokeSensor,
    ServicesTypes.CARBON_MONOXIDE_SENSOR: HomeKitCarbonMonoxideSensor,
    ServicesTypes.OCCUPANCY_SENSOR: HomeKitOccupancySensor,
    ServicesTypes.LEAK_SENSOR: HomeKitLeakSensor,
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Homekit lighting."""
    hkid = config_entry.data["AccessoryPairingID"]
    conn = hass.data[KNOWN_DEVICES][hkid]

    @callback
    def async_add_service(service):
        entity_class = ENTITY_TYPES.get(service.short_type)
        if not entity_class:
            return False
        info = {"aid": service.accessory.aid, "iid": service.iid}
        async_add_entities([entity_class(conn, info)], True)
        return True

    conn.add_listener(async_add_service)
