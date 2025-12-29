"""The read-only sensors for Hypontech integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from hyponcloud import OverviewData

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import HypontechConfigEntry
from .const import DOMAIN
from .coordinator import HypontechDataCoordinator


@dataclass(frozen=True, kw_only=True)
class HypontechSensorDescription(SensorEntityDescription):
    """Describes Hypontech Inverter sensor entity."""

    value_fn: Callable[[OverviewData], float | None]


SENSORS: tuple[HypontechSensorDescription, ...] = (
    HypontechSensorDescription(
        key="pv_power",
        translation_key="pv_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: c.power,
    ),
    HypontechSensorDescription(
        key="lifetime_energy",
        translation_key="lifetime_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda c: c.e_total,
    ),
    HypontechSensorDescription(
        key="today_energy",
        translation_key="today_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda c: c.e_today,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HypontechConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    coordinator = config_entry.runtime_data.coordinator

    async_add_entities(
        HypontechSensorWithDescription(coordinator, desc) for desc in SENSORS
    )


class HypontechSensorWithDescription(
    CoordinatorEntity[HypontechDataCoordinator], SensorEntity
):
    """Class describing Hypontech sensor entities."""

    entity_description: HypontechSensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: HypontechDataCoordinator,
        description: HypontechSensorDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
        )

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data.overview_data)
