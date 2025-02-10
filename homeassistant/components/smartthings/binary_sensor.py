"""Support for binary sensors through the SmartThings cloud API."""

from __future__ import annotations

from dataclasses import dataclass

from pysmartthings.models import Attribute, Capability

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import SmartThingsConfigEntry, SmartThingsDeviceCoordinator
from .entity import SmartThingsEntity

# CAPABILITY_TO_ATTRIB = {
#     Capability.acceleration_sensor: Attribute.acceleration,
#     Capability.contact_sensor: Attribute.contact,
#     Capability.filter_status: Attribute.filter_status,
#     Capability.motion_sensor: Attribute.motion,
#     Capability.presence_sensor: Attribute.presence,
#     Capability.sound_sensor: Attribute.sound,
#     Capability.tamper_alert: Attribute.tamper,
#     Capability.valve: Attribute.valve,
#     Capability.water_sensor: Attribute.water,
# }
# ATTRIB_TO_CLASS = {
#     Attribute.acceleration: BinarySensorDeviceClass.MOVING,
#     Attribute.contact: BinarySensorDeviceClass.OPENING,
#     Attribute.filter_status: BinarySensorDeviceClass.PROBLEM,
#     Attribute.motion: BinarySensorDeviceClass.MOTION,
#     Attribute.presence: BinarySensorDeviceClass.PRESENCE,
#     Attribute.sound: BinarySensorDeviceClass.SOUND,
#     Attribute.tamper: BinarySensorDeviceClass.PROBLEM,
#     Attribute.valve: BinarySensorDeviceClass.OPENING,
#     Attribute.water: BinarySensorDeviceClass.MOISTURE,
# }
# ATTRIB_TO_ENTITY_CATEGORY = {
#     Attribute.tamper: EntityCategory.DIAGNOSTIC,
# }
# ATTRIBUTE_ON_VALUES = {
#     Attribute.acceleration: "active",
#     Attribute.contact: "open",
#     Attribute.filter_status: "replace",
#     Attribute.motion: "active",
#     Attribute.mute: "muted",
#     Attribute.playback_shuffle: "enabled",
#     Attribute.presence: "present",
#     Attribute.sound: "detected",
#     Attribute.switch: "on",
#     Attribute.tamper: "detected",
#     Attribute.valve: "open",
#     Attribute.water: "wet",
# }


@dataclass(frozen=True, kw_only=True)
class SmartThingsBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describe a SmartThings binary sensor entity."""

    is_on_key: str


CAPABILITY_TO_SENSORS: dict[
    Capability, dict[Attribute, list[SmartThingsBinarySensorEntityDescription]]
] = {
    Capability.MOTION_SENSOR: {
        Attribute.MOTION: [
            SmartThingsBinarySensorEntityDescription(
                key=Attribute.MOTION,
                device_class=BinarySensorDeviceClass.MOTION,
                is_on_key="active",
            )
        ]
    },
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
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SmartThingsConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add binary sensors for a config entry."""
    devices = entry.runtime_data.devices
    async_add_entities(
        SmartThingsBinarySensor(device, description, capability, attribute)
        for device in devices
        for capability, attributes in device.data.items()
        if capability in CAPABILITY_TO_SENSORS
        for attribute in attributes
        for description in CAPABILITY_TO_SENSORS[capability].get(attribute, [])
    )
    # broker = hass.data[DOMAIN][DATA_BROKERS][config_entry.entry_id]
    # sensors = []
    # for device in broker.devices.values():
    #     for capability in broker.get_assigned(device.device_id, "binary_sensor"):
    #         attrib = CAPABILITY_TO_ATTRIB[capability]
    #         sensors.append(SmartThingsBinarySensor(device, attrib))
    # async_add_entities(sensors)


#
# def get_capabilities(capabilities: Sequence[str]) -> Sequence[str] | None:
#     """Return all capabilities supported if minimum required are present."""
#     return [
#         capability for capability in CAPABILITY_TO_ATTRIB if capability in capabilities
#     ]


class SmartThingsBinarySensor(SmartThingsEntity, BinarySensorEntity):
    """Define a SmartThings Binary Sensor."""

    entity_description: SmartThingsBinarySensorEntityDescription

    def __init__(
        self,
        device: SmartThingsDeviceCoordinator,
        entity_description: SmartThingsBinarySensorEntityDescription,
        capability: Capability,
        attribute: Attribute,
    ) -> None:
        """Init the class."""
        super().__init__(device)
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
