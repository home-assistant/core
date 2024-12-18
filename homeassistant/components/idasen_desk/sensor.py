"""Representation of Idasen Desk sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfLength
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import IdasenDeskConfigEntry, IdasenDeskCoordinator
from .entity import IdasenDeskEntity


@dataclass(frozen=True, kw_only=True)
class IdasenDeskSensorDescription(SensorEntityDescription):
    """Class describing IdasenDesk sensor entities."""

    value_fn: Callable[[IdasenDeskCoordinator], float | None]


SENSORS = (
    IdasenDeskSensorDescription(
        key="height",
        translation_key="height",
        native_unit_of_measurement=UnitOfLength.METERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        suggested_display_precision=3,
        value_fn=lambda coordinator: coordinator.desk.height,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IdasenDeskConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Idasen Desk sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        IdasenDeskSensor(coordinator, sensor_description)
        for sensor_description in SENSORS
    )


class IdasenDeskSensor(IdasenDeskEntity, SensorEntity):
    """IdasenDesk sensor."""

    entity_description: IdasenDeskSensorDescription

    def __init__(
        self,
        coordinator: IdasenDeskCoordinator,
        description: IdasenDeskSensorDescription,
    ) -> None:
        """Initialize the IdasenDesk sensor entity."""
        super().__init__(f"{description.key}-{coordinator.address}", coordinator)
        self.entity_description = description

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self._update_native_value()

    @callback
    def _handle_coordinator_update(self, *args: Any) -> None:
        """Handle data update."""
        self._update_native_value()
        super()._handle_coordinator_update()

    def _update_native_value(self) -> None:
        """Update the native value attribute."""
        self._attr_native_value = self.entity_description.value_fn(self.coordinator)
