"""Support for Rheem EcoNet water heaters."""

from typing import override

from pyeconet.equipment import Equipment, EquipmentType

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import EconetConfigEntry
from .entity import EcoNetEntity

BINARY_SENSOR_TYPES: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key="shutoff_valve_open",
        translation_key="shutoff_valve",
        device_class=BinarySensorDeviceClass.OPENING,
    ),
    BinarySensorEntityDescription(
        key="running",
        translation_key="running",
        device_class=BinarySensorDeviceClass.POWER,
    ),
    BinarySensorEntityDescription(
        key="screen_locked",
        translation_key="screen_locked",
        device_class=BinarySensorDeviceClass.LOCK,
    ),
    BinarySensorEntityDescription(
        key="beep_enabled",
        translation_key="beep_enabled",
        device_class=BinarySensorDeviceClass.SOUND,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EconetConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up EcoNet binary sensor based on a config entry."""
    equipment = entry.runtime_data
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

    _attr_has_entity_name = True

    def __init__(
        self, econet_device: Equipment, description: BinarySensorEntityDescription
    ) -> None:
        """Initialize."""
        super().__init__(econet_device)
        self.entity_description = description
        # Translation keys are also legacy unique-ID suffixes and must stay stable.
        self._attr_unique_id = f"{econet_device.device_id}_{econet_device.device_name}_{description.translation_key}"

    @property
    @override
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return getattr(self._econet, self.entity_description.key)
