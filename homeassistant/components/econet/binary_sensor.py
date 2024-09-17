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

from .const import DOMAIN, EQUIPMENT
from .entity import EcoNetEntity

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

    def __init__(
        self, econet_device, description: BinarySensorEntityDescription
    ) -> None:
        """Initialize."""
        super().__init__(econet_device)
        self.entity_description = description
        self._attr_name = f"{econet_device.device_name}_{description.name}"
        self._attr_unique_id = (
            f"{econet_device.device_id}_{econet_device.device_name}_{description.name}"
        )

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return getattr(self._econet, self.entity_description.key)
