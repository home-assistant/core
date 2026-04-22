"""Sensor platform for the Rotarex integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from rotarex_dimes_srg_api import RotarexTank

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import RotarexConfigEntry
from .const import DOMAIN
from .coordinator import RotarexDataUpdateCoordinator, RotarexTankData


def get_tank_name(tank: RotarexTank) -> str:
    """Return a user-friendly name for the tank."""
    if tank.name:
        return tank.name
    return f"Tank {tank.guid}"


@dataclass(kw_only=True, frozen=True)
class RotarexTankSensorEntityDescription(SensorEntityDescription):
    """Entity description for Rotarex tank sensors."""

    value_fn: Callable[[RotarexTankData], float | datetime | None]


SENSOR_DESCRIPTIONS: tuple[RotarexTankSensorEntityDescription, ...] = (
    RotarexTankSensorEntityDescription(
        key="level",
        translation_key="level",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: (
            data.latest_sync.level if data.latest_sync is not None else None
        ),
    ),
    RotarexTankSensorEntityDescription(
        key="battery",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: (
            data.latest_sync.battery if data.latest_sync is not None else None
        ),
    ),
    RotarexTankSensorEntityDescription(
        key="last_sync",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: data.latest_sync_dt,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: RotarexConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Rotarex sensors from a config entry."""
    coordinator = config_entry.runtime_data

    entities = [
        RotarexTankSensor(coordinator, tank_id, description)
        for tank_id in coordinator.data
        for description in SENSOR_DESCRIPTIONS
    ]
    async_add_entities(entities)


class RotarexTankSensor(CoordinatorEntity[RotarexDataUpdateCoordinator], SensorEntity):
    """Representation of a Rotarex tank sensor."""

    entity_description: RotarexTankSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: RotarexDataUpdateCoordinator,
        tank_id: str,
        description: RotarexTankSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._tank_id = tank_id
        self._attr_unique_id = f"{tank_id}_{description.key}"

        tank_data = coordinator.data[tank_id]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, tank_id)},
            name=get_tank_name(tank_data.tank),
            manufacturer="Rotarex",
            model="DIMES SRG",
        )

    @property
    def _tank_data(self) -> RotarexTankData | None:
        # A tank can disappear from coordinator data if the API stops returning
        # it (stale device). The entity becomes unavailable in that case.
        return self.coordinator.data.get(self._tank_id)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        tank_data = self._tank_data
        return (
            super().available
            and tank_data is not None
            and tank_data.latest_sync is not None
        )

    @property
    def native_value(self) -> float | datetime | None:
        """Return the state of the sensor."""
        tank_data = self._tank_data
        if tank_data is None:
            return None
        return self.entity_description.value_fn(tank_data)
