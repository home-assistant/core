"""The read-only sensors for APsystems local API integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import HypontechDataCoordinator
from .hyponcloud import PlantData


@dataclass(frozen=True, kw_only=True)
class HypontechSensorDescription(SensorEntityDescription):
    """Describes Hypontech Inverter sensor entity."""

    value_fn: Callable[[PlantData], float | None]


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
        key="lifetime_production",
        translation_key="lifetime_production",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda c: c.e_total,
    ),
    HypontechSensorDescription(
        key="today_production",
        translation_key="today_production",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda c: c.e_today,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    config = config_entry.runtime_data

    async_add_entities(HypontechSensorWithDescription(config, desc) for desc in SENSORS)


class HypontechSensorWithDescription(
    CoordinatorEntity[HypontechDataCoordinator], SensorEntity
):
    """Class describing Hypontech sensor entities."""

    entity_description: HypontechSensorDescription
