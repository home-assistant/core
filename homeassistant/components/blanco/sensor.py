"""Sensor platform for the BLANCO integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, override

from blanco_smart_home_api_client import BLANCO_DEVICE_NAMES, BlancoErrorType

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
    StateType,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import BlancoConfigEntry, BlancoDataUpdateCoordinator

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class BlancoSensorEntityDescription(SensorEntityDescription):
    """Describes a BLANCO sensor entity."""

    value_fn: Callable[[dict[str, Any]], StateType]


def _count_errors(data: dict[str, Any], severity: BlancoErrorType) -> int:
    """Return the number of active device errors with the given severity."""
    return sum(
        1
        for error in data["errors"].get("errors", [])
        if error.get("err_type") == severity
    )


SENSOR_DESCRIPTIONS: tuple[BlancoSensorEntityDescription, ...] = (
    BlancoSensorEntityDescription(
        key="error_count_critical",
        translation_key="error_count_critical",
        value_fn=lambda data: _count_errors(data, BlancoErrorType.CRITICAL),
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BlancoSensorEntityDescription(
        key="error_count_warning",
        translation_key="error_count_warning",
        value_fn=lambda data: _count_errors(data, BlancoErrorType.WARNING),
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BlancoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up BLANCO sensors from a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        BlancoSensorEntity(coordinator, description)
        for description in SENSOR_DESCRIPTIONS
    )


class BlancoSensorEntity(CoordinatorEntity[BlancoDataUpdateCoordinator], SensorEntity):
    """A sensor entity for a BLANCO device."""

    entity_description: BlancoSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: BlancoDataUpdateCoordinator,
        description: BlancoSensorEntityDescription,
    ) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.dev_id}_{description.key}"
        system_params: dict[str, Any] = coordinator.data["system"].get("params", {})
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.dev_id)},
            name=system_params.get("dev_name", "BLANCO"),
            manufacturer="BLANCO",
            model=(
                BLANCO_DEVICE_NAMES.get(coordinator.dev_type)
                if coordinator.dev_type is not None
                else None
            ),
            serial_number=coordinator.serial,
            sw_version=system_params.get("sw_ver_main_con"),
        )

    @override
    @property
    def native_value(self) -> StateType:
        """Return the current sensor value."""
        return self.entity_description.value_fn(self.coordinator.data)
