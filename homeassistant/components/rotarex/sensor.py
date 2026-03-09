"""Sensor platform for the Rotarex integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

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
from homeassistant.util import dt as dt_util

from . import RotarexConfigEntry
from .const import DOMAIN
from .coordinator import RotarexDataUpdateCoordinator
from .models import RotarexSyncData, RotarexTank


def get_tank_name(tank: RotarexTank) -> str:
    """Return a user-friendly name for the tank."""
    if tank.name:
        return tank.name
    return f"Tank {tank.guid}"


@dataclass(kw_only=True, frozen=True)
class RotarexTankSensorEntityDescription(SensorEntityDescription):
    """Entity description for Rotarex tank sensors."""

    value_fn: Callable[[RotarexSyncData], float | str | None]


SENSOR_DESCRIPTIONS: tuple[RotarexTankSensorEntityDescription, ...] = (
    RotarexTankSensorEntityDescription(
        key="level",
        translation_key="level",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda sync: sync.level,
    ),
    RotarexTankSensorEntityDescription(
        key="battery",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda sync: sync.battery,
    ),
    RotarexTankSensorEntityDescription(
        key="last_sync",
        translation_key="last_sync",
        value_fn=lambda sync: (
            parsed.strftime("%Y-%m-%d %H:%M:%S")
            if (parsed := dt_util.parse_datetime(sync.synch_date)) is not None
            else None
        ),
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

        # Get initial tank data for device info
        tank = coordinator.data[tank_id]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, tank_id)},
            name=get_tank_name(tank),
            manufacturer="Rotarex",
            model="DIMES SRG",
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self._get_latest_sync() is not None

    @property
    def native_value(self) -> float | str | None:
        """Return the state of the sensor."""
        if (sync := self._get_latest_sync()) is None:
            return None
        return self.entity_description.value_fn(sync)

    def _get_latest_sync(self) -> RotarexSyncData | None:
        """Return the most recent synchronization entry for the tank."""
        tank = self.coordinator.data.get(self._tank_id)
        if not tank or not tank.synch_datas:
            return None

        # Parse synchronization dates to ensure correct chronological ordering.
        parsed_syncs: list[tuple[RotarexSyncData, datetime]] = []
        for sync in tank.synch_datas:
            parsed = dt_util.parse_datetime(sync.synch_date)
            if parsed is not None:
                parsed_syncs.append((sync, parsed))

        if not parsed_syncs:
            return None

        latest_sync, _ = max(parsed_syncs, key=lambda item: item[1])
        return latest_sync
