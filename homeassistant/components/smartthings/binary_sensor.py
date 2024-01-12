"""Support for binary sensors through the SmartThings cloud API."""
from __future__ import annotations

from collections.abc import Sequence

from pysmartthings import Attribute, Capability

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SmartThingsEntity
from .const import DATA_BROKERS, DOMAIN
from .utils import format_component_name, get_device_attributes, get_device_status

CAPABILITY_TO_ATTRIB = {
    Capability.acceleration_sensor: Attribute.acceleration,
    Capability.contact_sensor: Attribute.contact,
    Capability.filter_status: Attribute.filter_status,
    Capability.motion_sensor: Attribute.motion,
    Capability.presence_sensor: Attribute.presence,
    Capability.sound_sensor: Attribute.sound,
    Capability.switch: Attribute.power,
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
    Attribute.power: BinarySensorDeviceClass.POWER,
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
        capabilities = broker.get_assigned(device.device_id, Platform.BINARY_SENSOR)
        device_components = get_device_attributes(device)

        for component_id in list(device_components.keys()):
            attributes = device_components[component_id]

            for capability in capabilities:
                attrib = CAPABILITY_TO_ATTRIB[capability]

                if attributes is None or attrib in attributes:
                    sensors.append(
                        SmartThingsBinarySensor(device, attrib, component_id)
                    )

    async_add_entities(sensors)


def get_capabilities(capabilities: Sequence[str]) -> Sequence[str] | None:
    """Return all capabilities supported if minimum required are present."""
    return [
        capability for capability in CAPABILITY_TO_ATTRIB if capability in capabilities
    ]


class SmartThingsBinarySensor(SmartThingsEntity, BinarySensorEntity):
    """Define a SmartThings Binary Sensor."""

    def __init__(self, device, attribute, component_id: str | None = None) -> None:
        """Init the class."""
        super().__init__(device)
        self._attribute = attribute
        self._component_id = component_id

        self._attr_name = format_component_name(device.label, attribute, component_id)
        self._attr_unique_id = format_component_name(
            device.device_id, attribute, component_id, "."
        )

        self._attr_device_class = ATTRIB_TO_CLASS[attribute]
        self._attr_entity_category = ATTRIB_TO_ENTTIY_CATEGORY.get(attribute)

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        status = get_device_status(self._device, self._component_id)

        if status is None:
            return False

        return status.is_on(self._attribute)
