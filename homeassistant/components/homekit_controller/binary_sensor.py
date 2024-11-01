"""Support for Homekit motion sensors."""

from __future__ import annotations

from aiohomekit.model.characteristics import CharacteristicsTypes
from aiohomekit.model.services import Service, ServicesTypes

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import KNOWN_DEVICES
from .connection import HKDevice
from .entity import HomeKitEntity


class HomeKitMotionSensor(HomeKitEntity, BinarySensorEntity):
    """Representation of a Homekit motion sensor."""

    _attr_device_class = BinarySensorDeviceClass.MOTION

    def get_characteristic_types(self) -> list[str]:
        """Define the homekit characteristics the entity is tracking."""
        return [CharacteristicsTypes.MOTION_DETECTED]

    @property
    def is_on(self) -> bool:
        """Has motion been detected."""
        return self.service.value(CharacteristicsTypes.MOTION_DETECTED) is True


class HomeKitContactSensor(HomeKitEntity, BinarySensorEntity):
    """Representation of a Homekit contact sensor."""

    _attr_device_class = BinarySensorDeviceClass.OPENING

    def get_characteristic_types(self) -> list[str]:
        """Define the homekit characteristics the entity is tracking."""
        return [CharacteristicsTypes.CONTACT_STATE]

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on/open."""
        return self.service.value(CharacteristicsTypes.CONTACT_STATE) == 1


class HomeKitSmokeSensor(HomeKitEntity, BinarySensorEntity):
    """Representation of a Homekit smoke sensor."""

    _attr_device_class = BinarySensorDeviceClass.SMOKE

    def get_characteristic_types(self) -> list[str]:
        """Define the homekit characteristics the entity is tracking."""
        return [CharacteristicsTypes.SMOKE_DETECTED]

    @property
    def is_on(self) -> bool:
        """Return true if smoke is currently detected."""
        return self.service.value(CharacteristicsTypes.SMOKE_DETECTED) == 1


class HomeKitCarbonMonoxideSensor(HomeKitEntity, BinarySensorEntity):
    """Representation of a Homekit BO sensor."""

    _attr_device_class = BinarySensorDeviceClass.CO

    def get_characteristic_types(self) -> list[str]:
        """Define the homekit characteristics the entity is tracking."""
        return [CharacteristicsTypes.CARBON_MONOXIDE_DETECTED]

    @property
    def is_on(self) -> bool:
        """Return true if CO is currently detected."""
        return self.service.value(CharacteristicsTypes.CARBON_MONOXIDE_DETECTED) == 1


class HomeKitOccupancySensor(HomeKitEntity, BinarySensorEntity):
    """Representation of a Homekit occupancy sensor."""

    _attr_device_class = BinarySensorDeviceClass.OCCUPANCY

    def get_characteristic_types(self) -> list[str]:
        """Define the homekit characteristics the entity is tracking."""
        return [CharacteristicsTypes.OCCUPANCY_DETECTED]

    @property
    def is_on(self) -> bool:
        """Return true if occupancy is currently detected."""
        return self.service.value(CharacteristicsTypes.OCCUPANCY_DETECTED) == 1


class HomeKitLeakSensor(HomeKitEntity, BinarySensorEntity):
    """Representation of a Homekit leak sensor."""

    _attr_device_class = BinarySensorDeviceClass.MOISTURE

    def get_characteristic_types(self) -> list[str]:
        """Define the homekit characteristics the entity is tracking."""
        return [CharacteristicsTypes.LEAK_DETECTED]

    @property
    def is_on(self) -> bool:
        """Return true if a leak is detected from the binary sensor."""
        return self.service.value(CharacteristicsTypes.LEAK_DETECTED) == 1


class HomeKitBatteryLowSensor(HomeKitEntity, BinarySensorEntity):
    """Representation of a Homekit battery low sensor."""

    _attr_device_class = BinarySensorDeviceClass.BATTERY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def get_characteristic_types(self) -> list[str]:
        """Define the homekit characteristics the entity is tracking."""
        return [CharacteristicsTypes.STATUS_LO_BATT]

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        if name := self.accessory.name:
            return f"{name} Low Battery"
        return "Low Battery"

    @property
    def is_on(self) -> bool:
        """Return true if low battery is detected from the binary sensor."""
        return self.service.value(CharacteristicsTypes.STATUS_LO_BATT) == 1


ENTITY_TYPES = {
    ServicesTypes.MOTION_SENSOR: HomeKitMotionSensor,
    ServicesTypes.CONTACT_SENSOR: HomeKitContactSensor,
    ServicesTypes.SMOKE_SENSOR: HomeKitSmokeSensor,
    ServicesTypes.CARBON_MONOXIDE_SENSOR: HomeKitCarbonMonoxideSensor,
    ServicesTypes.OCCUPANCY_SENSOR: HomeKitOccupancySensor,
    ServicesTypes.LEAK_SENSOR: HomeKitLeakSensor,
    ServicesTypes.BATTERY_SERVICE: HomeKitBatteryLowSensor,
}

# Only create the entity if it has the required characteristic
REQUIRED_CHAR_BY_TYPE = {
    ServicesTypes.BATTERY_SERVICE: CharacteristicsTypes.STATUS_LO_BATT,
}
# Reject the service as another platform can represent it better
# if it has a specific characteristic
REJECT_CHAR_BY_TYPE = {
    ServicesTypes.BATTERY_SERVICE: CharacteristicsTypes.BATTERY_LEVEL,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Homekit lighting."""
    hkid: str = config_entry.data["AccessoryPairingID"]
    conn: HKDevice = hass.data[KNOWN_DEVICES][hkid]

    @callback
    def async_add_service(service: Service) -> bool:
        if not (entity_class := ENTITY_TYPES.get(service.type)):
            return False
        if (
            required_char := REQUIRED_CHAR_BY_TYPE.get(service.type)
        ) and not service.has(required_char):
            return False
        if (reject_char := REJECT_CHAR_BY_TYPE.get(service.type)) and service.has(
            reject_char
        ):
            return False
        info = {"aid": service.accessory.aid, "iid": service.iid}
        entity: HomeKitEntity = entity_class(conn, info)
        conn.async_migrate_unique_id(
            entity.old_unique_id, entity.unique_id, Platform.BINARY_SENSOR
        )
        async_add_entities([entity])
        return True

    conn.add_listener(async_add_service)
