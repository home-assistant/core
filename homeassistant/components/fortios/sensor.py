"""Support for FortiOS sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import FortiOSConfigEntry
from .const import DOMAIN
from .coordinator import FortiOSDataUpdateCoordinator

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class FortiOSSensorEntityDescription(SensorEntityDescription):
    """Class describing FortiOS sensor entities."""

    value_fn: Callable[[dict[str, Any]], StateType]


SENSORS: tuple[FortiOSSensorEntityDescription, ...] = (
    FortiOSSensorEntityDescription(
        key="cpu",
        translation_key="cpu",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("system_usage", {})
        .get("cpu", {})
        .get("current"),
    ),
    FortiOSSensorEntityDescription(
        key="memory",
        translation_key="memory",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("system_usage", {})
        .get("mem", {})
        .get("current"),
    ),
    FortiOSSensorEntityDescription(
        key="sessions",
        translation_key="sessions",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("system_usage", {})
        .get("session", {})
        .get("current"),
    ),
    FortiOSSensorEntityDescription(
        key="session_setup_rate",
        translation_key="session_setup_rate",
        native_unit_of_measurement="sessions/s",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: (
            data.get("system_usage", {}).get("setuprate", {}).get("current")
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FortiOSConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up FortiOS sensor platform."""
    coordinator = entry.runtime_data

    async_add_entities(
        FortiOSSensor(coordinator, description) for description in SENSORS
    )


class FortiOSSensor(CoordinatorEntity[FortiOSDataUpdateCoordinator], SensorEntity):
    """Representation of a FortiOS sensor."""

    entity_description: FortiOSSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: FortiOSDataUpdateCoordinator,
        description: FortiOSSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.serial}_{description.key}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info, keeping firmware version and serial number current."""
        system_status = self.coordinator.data.get("system_status", {})
        results = system_status.get("results", {})
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.serial or "")},
            name=results.get("hostname") or self.coordinator.config_entry.title,
            manufacturer="Fortinet",
            model="FortiGate",
            sw_version=system_status.get("version"),
            serial_number=self.coordinator.serial,
        )

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
