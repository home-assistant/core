"""Support for HomeKit binary sensors."""

from dataclasses import dataclass

from aiohomekit.model.characteristics import Characteristic, CharacteristicsTypes
from aiohomekit.model.services import Service, ServicesTypes

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import ConfigType

from . import KNOWN_DEVICES
from .connection import HKDevice
from .entity import CharacteristicEntity, HomeKitEntity
from .utils import service_feature_scope, service_feature_translation


@dataclass(frozen=True)
class HomeKitBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes a HomeKit binary sensor."""

    on_value: int | bool = 1


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

CHARACTERISTIC_BINARY_SENSORS: dict[str, HomeKitBinarySensorEntityDescription] = {
    CharacteristicsTypes.STATUS_LO_BATT: HomeKitBinarySensorEntityDescription(
        key=CharacteristicsTypes.STATUS_LO_BATT,
        has_entity_name=True,
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    CharacteristicsTypes.STATUS_FAULT: HomeKitBinarySensorEntityDescription(
        key=CharacteristicsTypes.STATUS_FAULT,
        has_entity_name=True,
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
}


class CharacteristicBinarySensor(CharacteristicEntity, BinarySensorEntity):
    """Representation of a HomeKit binary sensor backed by a single characteristic."""

    entity_description: HomeKitBinarySensorEntityDescription

    def __init__(
        self,
        conn: HKDevice,
        info: ConfigType,
        char: Characteristic,
        description: HomeKitBinarySensorEntityDescription,
    ) -> None:
        """Initialise a HomeKit characteristic binary sensor."""
        self.entity_description = description
        super().__init__(conn, info, char)
        if description.has_entity_name and (
            translation := service_feature_translation(
                char.service, description.translation_key or description.device_class
            )
        ):
            self._attr_translation_key, translation_placeholders = translation
            self._attr_translation_placeholders = translation_placeholders

    def get_characteristic_types(self) -> list[str]:
        """Define the homekit characteristics the entity is tracking."""
        return [self._char.type]

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return self._char.value == self.entity_description.on_value


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up HomeKit binary sensors."""
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

    @callback
    def async_add_characteristic(char: Characteristic) -> bool:
        if char.service.type == ServicesTypes.BATTERY_SERVICE:
            return False
        if not (description := CHARACTERISTIC_BINARY_SENSORS.get(char.type)):
            return False
        if char.type == CharacteristicsTypes.STATUS_LO_BATT and (
            _should_skip_low_battery_characteristic(char)
        ):
            return False

        info = {"aid": char.service.accessory.aid, "iid": char.service.iid}
        entity = CharacteristicBinarySensor(conn, info, char, description)
        conn.async_migrate_unique_id(
            entity.old_unique_id, entity.unique_id, Platform.BINARY_SENSOR
        )
        async_add_entities([entity])
        return True

    conn.add_char_factory(async_add_characteristic)


def _should_skip_low_battery_characteristic(char: Characteristic) -> bool:
    """Check if the low battery characteristic should not create an entity."""
    return char.service.accessory.services.first(
        service_type=ServicesTypes.BATTERY_SERVICE
    ) is not None or _has_earlier_low_battery_characteristic(char)


def _has_earlier_low_battery_characteristic(char: Characteristic) -> bool:
    """Check if the accessory already exposed the same low battery source.

    Unscoped low battery characteristics are treated as accessory-level duplicates.
    """
    source_key = _low_battery_source_key(char.service)
    return any(
        service.iid < char.service.iid
        and service.has(char.type)
        and _low_battery_source_key(service) == source_key
        for service in char.service.accessory.services
    )


def _low_battery_source_key(service: Service) -> str | None:
    """Return the low battery source key for the service."""
    if scope := service_feature_scope(service):
        return scope.key
    return None
