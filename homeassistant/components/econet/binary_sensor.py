"""Support for Rheem EcoNet water heaters."""
import logging

from pyeconet.equipment import EquipmentType

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_LOCK,
    DEVICE_CLASS_OPENING,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_SOUND,
    BinarySensorEntity,
)

from . import EcoNetEntity
from .const import DOMAIN, EQUIPMENT

SENSOR_NAME_SHUTOFF_VALVE = "shutoff_valve"
SENSOR_NAME_RUNNING = "running"
SENSOR_NAME_SCREEN_LOCKED = "screen_locked"
SENSOR_NAME_BEEP_ENABLED = "beep_enabled"

SENSOR_NAMES_TO_ATTRIBUTES = {
    SENSOR_NAME_SHUTOFF_VALVE: "shutoff_valve_open",
    SENSOR_NAME_RUNNING: "running",
    SENSOR_NAME_SCREEN_LOCKED: "screen_locked",
    SENSOR_NAME_BEEP_ENABLED: "beep_enabled",
}

SENSOR_NAMES_TO_DEVICE_CLASS = {
    SENSOR_NAME_SHUTOFF_VALVE: DEVICE_CLASS_OPENING,
    SENSOR_NAME_RUNNING: DEVICE_CLASS_POWER,
    SENSOR_NAME_BEEP_ENABLED: DEVICE_CLASS_SOUND,
    SENSOR_NAME_SCREEN_LOCKED: DEVICE_CLASS_LOCK,
}

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up EcoNet binary sensor based on a config entry."""
    equipment = hass.data[DOMAIN][EQUIPMENT][entry.entry_id]
    binary_sensors = []
    all_equipment = equipment[EquipmentType.WATER_HEATER]
    all_equipment.extend(equipment[EquipmentType.THERMOSTAT])
    for _equip in all_equipment:
        for name, attribute in SENSOR_NAMES_TO_ATTRIBUTES.items():
            if getattr(_equip, attribute, None) is not None:
                binary_sensors.append(EcoNetBinarySensor(_equip, name))
    async_add_entities(
        binary_sensors,
    )


class EcoNetBinarySensor(EcoNetEntity, BinarySensorEntity):
    """Define a Econet binary sensor."""

    def __init__(self, econet_device, device_name):
        """Initialize."""
        super().__init__(econet_device)
        self._econet = econet_device
        self._device_name = device_name

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return getattr(self._econet, SENSOR_NAMES_TO_ATTRIBUTES[self._device_name])

    @property
    def device_class(self):
        """Return the class of this sensor, from DEVICE_CLASSES."""
        return SENSOR_NAMES_TO_DEVICE_CLASS[self._device_name]

    @property
    def name(self):
        """Return the name of the entity."""
        return f"{self._econet.device_name}_{self._device_name}"

    @property
    def unique_id(self):
        """Return the unique ID of the entity."""
        return (
            f"{self._econet.device_id}_{self._econet.device_name}_{self._device_name}"
        )
