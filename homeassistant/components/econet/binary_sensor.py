"""Support for Rheem EcoNet water heaters."""
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

SENSOR_NAME_RUNNING = "running"
SENSOR_NAME_SHUTOFF_VALVE = "shutoff_valve"
SENSOR_NAME_RUNNING = "running"
SENSOR_NAME_SCREEN_LOCKED = "screen_locked"
SENSOR_NAME_BEEP_ENABLED = "beep_enabled"

ATTR = "attr"
DEVICE_CLASS = "device_class"
SENSORS = {
    SENSOR_NAME_SHUTOFF_VALVE: {
        ATTR: "shutoff_valve_open",
        DEVICE_CLASS: DEVICE_CLASS_OPENING,
    },
    SENSOR_NAME_RUNNING: {ATTR: "running", DEVICE_CLASS: DEVICE_CLASS_POWER},
    SENSOR_NAME_SCREEN_LOCKED: {
        ATTR: "screen_locked",
        DEVICE_CLASS: DEVICE_CLASS_LOCK,
    },
    SENSOR_NAME_BEEP_ENABLED: {
        ATTR: "beep_enabled",
        DEVICE_CLASS: DEVICE_CLASS_SOUND,
    },
}


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up EcoNet binary sensor based on a config entry."""
    equipment = hass.data[DOMAIN][EQUIPMENT][entry.entry_id]
    binary_sensors = []
    all_equipment = equipment[EquipmentType.WATER_HEATER].copy()
    all_equipment.extend(equipment[EquipmentType.THERMOSTAT].copy())
    for _equip in all_equipment:
        for sensor_name, sensor in SENSORS.items():
            if getattr(_equip, sensor[ATTR], None) is not None:
                binary_sensors.append(EcoNetBinarySensor(_equip, sensor_name))

    async_add_entities(binary_sensors)


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
        return getattr(self._econet, SENSORS[self._device_name][ATTR])

    @property
    def device_class(self):
        """Return the class of this sensor, from DEVICE_CLASSES."""
        return SENSORS[self._device_name][DEVICE_CLASS]

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
