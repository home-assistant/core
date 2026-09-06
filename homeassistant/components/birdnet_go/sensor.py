"""Sensor platform for BirdNET-Go integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from aiobirdnetgo import DashboardKPIs

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEFAULT_NAME, DOMAIN
from .coordinator import BirdNetGoConfigEntry, BirdNetGoDataUpdateCoordinator

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class BirdNetGoSensorEntityDescription(SensorEntityDescription):
    """Describes BirdNET-Go sensor entity."""

    value_fn: Callable[[DashboardKPIs], int | float | None]


SENSOR_DESCRIPTIONS: tuple[BirdNetGoSensorEntityDescription, ...] = (
    BirdNetGoSensorEntityDescription(
        key="today_detections",
        translation_key="today_detections",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda kpis: kpis.today_detections,
    ),
    BirdNetGoSensorEntityDescription(
        key="lifetime_species",
        translation_key="lifetime_species",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda kpis: kpis.lifetime_species,
    ),
    BirdNetGoSensorEntityDescription(
        key="detection_streak",
        translation_key="detection_streak",
        native_unit_of_measurement=UnitOfTime.DAYS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda kpis: kpis.detection_streak.days,
    ),
    BirdNetGoSensorEntityDescription(
        key="best_day_count",
        translation_key="best_day_count",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda kpis: kpis.best_day.count,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BirdNetGoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up BirdNET-Go sensors based on a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        BirdNetGoSensor(coordinator, description) for description in SENSOR_DESCRIPTIONS
    )


class BirdNetGoSensor(CoordinatorEntity[BirdNetGoDataUpdateCoordinator], SensorEntity):
    """Representation of a BirdNET-Go sensor."""

    entity_description: BirdNetGoSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: BirdNetGoDataUpdateCoordinator,
        description: BirdNetGoSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            manufacturer=DEFAULT_NAME,
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=coordinator.client.base_url,
        )

    @property
    @override
    def native_value(self) -> int | float | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
