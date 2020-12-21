"""Support for Rheem EcoNet water heaters."""
import logging

from pyeconet.equipment import EquipmentType

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_OPENING,
    DEVICE_CLASS_POWER,
    BinarySensorEntity,
)

from . import EcoNetEntity
from .const import DOMAIN, EQUIPMENT

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up EcoNet binary sensor based on a config entry."""
    equipment = hass.data[DOMAIN][EQUIPMENT][entry.entry_id]
    binary_sensors = []
    for water_heater in equipment[EquipmentType.WATER_HEATER]:
        if water_heater.has_shutoff_valve:
            binary_sensors.append(
                EcoNetBinarySensor(
                    water_heater,
                    "shutoff_valve",
                )
            )
        if water_heater.running is not None:
            binary_sensors.append(EcoNetBinarySensor(water_heater, "running"))
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
        if self._device_name == "shutoff_valve":
            return self._econet.shutoff_valve_open
        if self._device_name == "running":
            return self._econet.running

    @property
    def device_class(self):
        """Return the class of this sensor, from DEVICE_CLASSES."""
        if self._device_name == "shutoff_valve":
            return DEVICE_CLASS_OPENING
        if self._device_name == "running":
            return DEVICE_CLASS_POWER

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
