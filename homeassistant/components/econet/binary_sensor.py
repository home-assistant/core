"""Support for Rheem EcoNet water heaters."""
from __future__ import annotations

from pyeconet.equipment import EquipmentType

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import EcoNetEntity
from .const import DOMAIN, EQUIPMENT

BINARY_SENSOR_TYPES: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key="shutoff_valve_open",
        name="shutoff_valve",
        device_class=BinarySensorDeviceClass.OPENING,
    ),
    BinarySensorEntityDescription(
        key="running",
        name="running",
        device_class=BinarySensorDeviceClass.POWER,
    ),
    BinarySensorEntityDescription(
        key="screen_locked",
        name="screen_locked",
        device_class=BinarySensorDeviceClass.LOCK,
    ),
    BinarySensorEntityDescription(
        key="beep_enabled",
        name="beep_enabled",
        device_class=BinarySensorDeviceClass.SOUND,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up EcoNet binary sensor based on a config entry."""
    equipment = hass.data[DOMAIN][EQUIPMENT][entry.entry_id]
    all_equipment = equipment[EquipmentType.WATER_HEATER].copy()
    all_equipment.extend(equipment[EquipmentType.THERMOSTAT].copy())

    entities = [
        EcoNetBinarySensor(_equip, description)
        for _equip in all_equipment
        for description in BINARY_SENSOR_TYPES
        if getattr(_equip, description.key, None) is not None
    ]

    async_add_entities(entities)


class EcoNetBinarySensor(EcoNetEntity, BinarySensorEntity):
    """Define a Econet binary sensor."""

    def __init__(self, econet_device, description: BinarySensorEntityDescription):
        """Initialize."""
        super().__init__(econet_device)
        self.entity_description = description
        self._econet = econet_device

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return getattr(self._econet, self.entity_description.key)

    @property
    def name(self):
        """Return the name of the entity."""
        return f"{self._econet.device_name}_{self.entity_description.name}"

    @property
    def unique_id(self):
        """Return the unique ID of the entity."""
        return f"{self._econet.device_id}_{self._econet.device_name}_{self.entity_description.name}"
