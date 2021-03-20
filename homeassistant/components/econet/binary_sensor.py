"""Support for Rheem EcoNet water heaters."""
from pyeconet.equipment import EquipmentType

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_OPENING,
    DEVICE_CLASS_POWER,
    BinarySensorEntity,
)

from . import EcoNetEntity
from .const import DOMAIN, EQUIPMENT

SENSOR_NAME_RUNNING = "running"
SENSOR_NAME_SHUTOFF_VALVE = "shutoff_valve"
SENSOR_NAME_VACATION = "vacation"


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up EcoNet binary sensor based on a config entry."""
    equipment = hass.data[DOMAIN][EQUIPMENT][entry.entry_id]
    binary_sensors = []
    for water_heater in equipment[EquipmentType.WATER_HEATER]:
        if water_heater.has_shutoff_valve:
            binary_sensors.append(
                EcoNetBinarySensor(
                    water_heater,
                    SENSOR_NAME_SHUTOFF_VALVE,
                )
            )
        if water_heater.running is not None:
            binary_sensors.append(EcoNetBinarySensor(water_heater, SENSOR_NAME_RUNNING))
        if water_heater.vacation is not None:
            binary_sensors.append(
                EcoNetBinarySensor(water_heater, SENSOR_NAME_VACATION)
            )
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
        if self._device_name == SENSOR_NAME_SHUTOFF_VALVE:
            return self._econet.shutoff_valve_open
        if self._device_name == SENSOR_NAME_RUNNING:
            return self._econet.running
        if self._device_name == SENSOR_NAME_VACATION:
            return self._econet.vacation
        return False

    @property
    def device_class(self):
        """Return the class of this sensor, from DEVICE_CLASSES."""
        if self._device_name == SENSOR_NAME_SHUTOFF_VALVE:
            return DEVICE_CLASS_OPENING
        if self._device_name == SENSOR_NAME_RUNNING:
            return DEVICE_CLASS_POWER
        return None

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
