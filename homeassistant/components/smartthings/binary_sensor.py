"""Support for binary sensors through the SmartThings cloud API."""

from __future__ import annotations

from dataclasses import dataclass

from pysmartthings import SmartThings
from pysmartthings.models import Attribute, Capability

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import FullDevice, SmartThingsConfigEntry
from .entity import SmartThingsEntity


@dataclass(frozen=True, kw_only=True)
class SmartThingsBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describe a SmartThings binary sensor entity."""

    is_on_key: str


CAPABILITY_TO_SENSORS: dict[
    Capability, dict[Attribute, list[SmartThingsBinarySensorEntityDescription]]
] = {
    Capability.ACCELERATION_SENSOR: {
        Attribute.ACCELERATION: [
            SmartThingsBinarySensorEntityDescription(
                key=Attribute.ACCELERATION,
                device_class=BinarySensorDeviceClass.MOVING,
                is_on_key="active",
            )
        ]
    },
    Capability.CONTACT_SENSOR: {
        Attribute.CONTACT: [
            SmartThingsBinarySensorEntityDescription(
                key=Attribute.CONTACT,
                device_class=BinarySensorDeviceClass.DOOR,
                is_on_key="open",
            )
        ]
    },
    Capability.FILTER_STATUS: {
        Attribute.FILTER_STATUS: [
            SmartThingsBinarySensorEntityDescription(
                key=Attribute.FILTER_STATUS,
                device_class=BinarySensorDeviceClass.PROBLEM,
                is_on_key="replace",
            )
        ]
    },
    Capability.MOTION_SENSOR: {
        Attribute.MOTION: [
            SmartThingsBinarySensorEntityDescription(
                key=Attribute.MOTION,
                device_class=BinarySensorDeviceClass.MOTION,
                is_on_key="active",
            )
        ]
    },
    Capability.PRESENCE_SENSOR: {
        Attribute.PRESENCE: [
            SmartThingsBinarySensorEntityDescription(
                key=Attribute.PRESENCE,
                device_class=BinarySensorDeviceClass.PRESENCE,
                is_on_key="present",
            )
        ]
    },
    Capability.SOUND_SENSOR: {
        Attribute.SOUND: [
            SmartThingsBinarySensorEntityDescription(
                key=Attribute.SOUND,
                device_class=BinarySensorDeviceClass.SOUND,
                is_on_key="detected",
            )
        ]
    },
    Capability.TAMPER_ALERT: {
        Attribute.TAMPER: [
            SmartThingsBinarySensorEntityDescription(
                key=Attribute.TAMPER,
                device_class=BinarySensorDeviceClass.PROBLEM,
                is_on_key="detected",
                entity_category=EntityCategory.DIAGNOSTIC,
            )
        ]
    },
    Capability.VALVE: {
        Attribute.VALVE: [
            SmartThingsBinarySensorEntityDescription(
                key=Attribute.VALVE,
                device_class=BinarySensorDeviceClass.OPENING,
                is_on_key="open",
            )
        ]
    },
    Capability.WATER_SENSOR: {
        Attribute.WATER: [
            SmartThingsBinarySensorEntityDescription(
                key=Attribute.WATER,
                device_class=BinarySensorDeviceClass.MOISTURE,
                is_on_key="wet",
            )
        ]
    },
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SmartThingsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add binary sensors for a config entry."""
    entry_data = entry.runtime_data
    async_add_entities(
        SmartThingsBinarySensor(
            entry_data.client, device, description, capability, attribute
        )
        for device in entry_data.devices.values()
        for capability, attributes in device.status["main"].items()
        if capability in CAPABILITY_TO_SENSORS
        for attribute in attributes
        for description in CAPABILITY_TO_SENSORS[capability].get(attribute, [])
    )


class SmartThingsBinarySensor(SmartThingsEntity, BinarySensorEntity):
    """Define a SmartThings Binary Sensor."""

    entity_description: SmartThingsBinarySensorEntityDescription

    def __init__(
        self,
        client: SmartThings,
        device: FullDevice,
        entity_description: SmartThingsBinarySensorEntityDescription,
        capability: Capability,
        attribute: Attribute,
    ) -> None:
        """Init the class."""
        super().__init__(client, device, [capability])
        self._attribute = attribute
        self.capability = capability
        self.entity_description = entity_description
        self._attr_name = f"{device.device.label} {attribute}"
        self._attr_unique_id = f"{device.device.device_id}.{attribute}"

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return (
            self.get_attribute_value(self.capability, self._attribute)
            == self.entity_description.is_on_key
        )
