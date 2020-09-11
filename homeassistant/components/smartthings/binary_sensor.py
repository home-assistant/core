"""Support for binary sensors through the SmartThings cloud API."""
from typing import Optional, Sequence

from pysmartthings import Attribute, Capability

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_SOUND,
    BinarySensorEntity,
)

from . import SmartThingsEntity
from .const import DATA_BROKERS, DOMAIN

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
    Attribute.acceleration: "moving",
    Attribute.contact: "opening",
    Attribute.filter_status: "problem",
    Attribute.motion: "motion",
    Attribute.presence: "presence",
    Attribute.sound: DEVICE_CLASS_SOUND,
    Attribute.tamper: "problem",
    Attribute.valve: "opening",
    Attribute.water: "moisture",
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Add binary sensors for a config entry."""
    broker = hass.data[DOMAIN][DATA_BROKERS][config_entry.entry_id]
    sensors = []
    for device in broker.devices.values():
        for capability in broker.get_assigned(device.device_id, "binary_sensor"):
            attrib = CAPABILITY_TO_ATTRIB[capability]
            sensors.append(SmartThingsBinarySensor(device, attrib))
    async_add_entities(sensors)


def get_capabilities(capabilities: Sequence[str]) -> Optional[Sequence[str]]:
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

    @property
    def name(self) -> str:
        """Return the name of the binary sensor."""
        return f"{self._device.label} {self._attribute}"

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{self._device.device_id}.{self._attribute}"

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._device.status.is_on(self._attribute)

    @property
    def device_class(self):
        """Return the class of this device."""
        return ATTRIB_TO_CLASS[self._attribute]
