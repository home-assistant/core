"""Support for binary sensors through the SmartThings cloud API."""

from __future__ import annotations

from collections.abc import Sequence

from pysmartthings import Attribute, Capability

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_BROKERS, DOMAIN
from .entity import SmartThingsEntity

CAPABILITY_TO_ATTRIB = {
    Capability.acceleration_sensor: Attribute.acceleration,
    Capability.contact_sensor: Attribute.contact,
    Capability.filter_status: Attribute.filter_status,
    Capability.motion_sensor: Attribute.motion,
    Capability.presence_sensor: Attribute.presence,
    Capability.sound_sensor: Attribute.sound,
    Capability.tamper_alert: Attribute.tamper,
    Capability.valve: Attribute.valve,
    Capability.water_sensor: Attribute.water,
}
ATTRIB_TO_CLASS = {
    Attribute.acceleration: BinarySensorDeviceClass.MOVING,
    Attribute.contact: BinarySensorDeviceClass.OPENING,
    Attribute.filter_status: BinarySensorDeviceClass.PROBLEM,
    Attribute.motion: BinarySensorDeviceClass.MOTION,
    Attribute.presence: BinarySensorDeviceClass.PRESENCE,
    Attribute.sound: BinarySensorDeviceClass.SOUND,
    Attribute.tamper: BinarySensorDeviceClass.PROBLEM,
    Attribute.valve: BinarySensorDeviceClass.OPENING,
    Attribute.water: BinarySensorDeviceClass.MOISTURE,
}
ATTRIB_TO_ENTTIY_CATEGORY = {
    Attribute.tamper: EntityCategory.DIAGNOSTIC,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add binary sensors for a config entry."""
    broker = hass.data[DOMAIN][DATA_BROKERS][config_entry.entry_id]
    sensors = []
    for device in broker.devices.values():
        for capability in broker.get_assigned(device.device_id, "binary_sensor"):
            attrib = CAPABILITY_TO_ATTRIB[capability]
            sensors.append(SmartThingsBinarySensor(device, attrib))
    async_add_entities(sensors)


def get_capabilities(capabilities: Sequence[str]) -> Sequence[str] | None:
    """Return all capabilities supported if minimum required are present."""
    return [
        capability for capability in CAPABILITY_TO_ATTRIB if capability in capabilities
    ]


class SmartThingsBinarySensor(SmartThingsEntity, BinarySensorEntity):
    """Define a SmartThings Binary Sensor."""

    def __init__(self, device, attribute):
        """Init the class."""
        super().__init__(device)
        self._attribute = attribute
        self._attr_name = f"{device.label} {attribute}"
        self._attr_unique_id = f"{device.device_id}.{attribute}"
        self._attr_device_class = ATTRIB_TO_CLASS[attribute]
        self._attr_entity_category = ATTRIB_TO_ENTTIY_CATEGORY.get(attribute)

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._device.status.is_on(self._attribute)
