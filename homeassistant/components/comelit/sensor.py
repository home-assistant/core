"""Support for sensors."""
from __future__ import annotations

from typing import Final

from aiocomelit import ComelitSerialBridgeObject
from aiocomelit.const import OTHER

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ComelitSerialBridge

SENSOR_TYPES: Final = (
    SensorEntityDescription(
        key="power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Comelit sensors."""

    coordinator: ComelitSerialBridge = hass.data[DOMAIN][config_entry.entry_id]

    entities: list[ComelitSensorEntity] = []
    for device in coordinator.data[OTHER].values():
        entities.extend(
            ComelitSensorEntity(coordinator, device, config_entry.entry_id, sensor_desc)
            for sensor_desc in SENSOR_TYPES
        )

    async_add_entities(entities)


class ComelitSensorEntity(CoordinatorEntity[ComelitSerialBridge], SensorEntity):
    """Sensor device."""

    _attr_has_entity_name = True
    entity_description: SensorEntityDescription

    def __init__(
        self,
        coordinator: ComelitSerialBridge,
        device: ComelitSerialBridgeObject,
        config_entry_entry_id: str,
        description: SensorEntityDescription,
    ) -> None:
        """Init sensor entity."""
        self._api = coordinator.api
        self._device = device
        super().__init__(coordinator)
        # Use config_entry.entry_id as base for unique_id
        # because no serial number or mac is available
        self._attr_unique_id = f"{config_entry_entry_id}-{device.index}"
        self._attr_device_info = coordinator.platform_device_info(device)

        self.entity_description = description

    @property
    def native_value(self) -> StateType:
        """Sensor value."""
        return getattr(
            self.coordinator.data[OTHER][self._device.index],
            self.entity_description.key,
        )
