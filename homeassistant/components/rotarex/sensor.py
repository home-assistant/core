"""Sensor platform for the Rotarex integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from . import RotarexConfigEntry
from .const import DOMAIN
from .coordinator import RotarexDataUpdateCoordinator


def get_tank_name(tank_data: dict[str, Any] | None) -> str:
    """Return a user-friendly name for the tank."""
    if tank_data and (name := tank_data.get("Name")):
        return name
    if tank_data and (guid := tank_data.get("Guid")):
        return f"Tank {guid}"
    return "Unknown tank"


@dataclass(kw_only=True, frozen=True)
class RotarexTankSensorEntityDescription(SensorEntityDescription):
    """Entity description for Rotarex tank sensors."""

    value_fn: Callable[[dict[str, Any] | None], Any]
    extra_attr_fn: Callable[[dict[str, Any] | None], dict[str, Any] | None] | None = (
        None
    )


SENSOR_DESCRIPTIONS: tuple[RotarexTankSensorEntityDescription, ...] = (
    RotarexTankSensorEntityDescription(
        key="level",
        translation_key="level",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda sync: sync["Level"] if sync else None,
        extra_attr_fn=lambda sync: (
            {
                "last_sync": sync["SynchDate"],
                "temperature": sync["Temperature"],
            }
            if sync
            else None
        ),
    ),
    RotarexTankSensorEntityDescription(
        key="battery",
        translation_key="battery",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda sync: sync["Battery"] if sync else None,
        extra_attr_fn=lambda sync: (
            {"last_sync": sync["SynchDate"]} if sync else None
        ),
    ),
    RotarexTankSensorEntityDescription(
        key="last_sync",
        translation_key="last_sync",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda sync: (
            dt_util.parse_datetime(sync["SynchDate"])
            if sync and sync["SynchDate"]
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
        RotarexTankSensor(coordinator, tank, description)
        for tank in coordinator.data
        if isinstance(tank, dict) and tank.get("Guid")
        for description in SENSOR_DESCRIPTIONS
    ]
    async_add_entities(entities)


class RotarexTankSensor(CoordinatorEntity[RotarexDataUpdateCoordinator], SensorEntity):
    """Representation of a Rotarex tank sensor."""

    __slots__ = ("_tank_id", "entity_description")
    entity_description: RotarexTankSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: RotarexDataUpdateCoordinator,
        tank_data: dict[str, Any],
        description: RotarexTankSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._tank_id = tank_data["Guid"]
        self._attr_unique_id = f"{self._tank_id}_{description.key}"
        self._update_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle coordinated data updates."""
        self._update_state()
        self.async_write_ha_state()

    def _get_latest_sync(self) -> dict[str, Any] | None:
        """Return the most recent synchronization entry for the tank."""
        tank = next(
            (
                item
                for item in self.coordinator.data
                if isinstance(item, dict) and item.get("Guid") == self._tank_id
            ),
            None,
        )
        if not tank:
            return None

        synch_datas = tank.get("SynchDatas")
        if not isinstance(synch_datas, list):
            return None

        valid_syncs = [
            sync
            for sync in synch_datas
            if isinstance(sync, dict) and sync["SynchDate"]
        ]
        if not valid_syncs:
            return None

        # Parse synchronization dates to ensure correct chronological ordering.
        parsed_syncs: list[tuple[dict[str, Any], datetime]] = []
        for sync in valid_syncs:
            parsed = dt_util.parse_datetime(sync["SynchDate"])
            if parsed is not None:
                parsed_syncs.append((sync, parsed))

        if not parsed_syncs:
            return None

        latest_sync, _ = max(parsed_syncs, key=lambda item: item[1])
        return latest_sync

    def _update_state(self) -> None:
        """Update native value and attributes."""
        latest_sync = self._get_latest_sync()
        self._attr_native_value = self.entity_description.value_fn(latest_sync)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return entity extra attributes."""
        if self.entity_description.extra_attr_fn:
            return self.entity_description.extra_attr_fn(self._get_latest_sync())
        return None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device registry information."""
        tank_data = next(
            (
                item
                for item in self.coordinator.data
                if isinstance(item, dict) and item.get("Guid") == self._tank_id
            ),
            None,
        )

        return DeviceInfo(
            identifiers={(DOMAIN, self._tank_id)},
            name=get_tank_name(tank_data),
            manufacturer="Rotarex",
            model="DIMES SRG",
        )
