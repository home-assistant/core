"""The read-only sensors for Hypontech integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from hyponcloud import OverviewData, PlantData

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import HypontechConfigEntry, HypontechDataCoordinator, HypontechPlant
from .entity import HypontechEntity, HypontechPlantEntity


def _power_unit(data: OverviewData | PlantData) -> str:
    """Return the unit of measurement for power based on the API unit."""
    return UnitOfPower.KILO_WATT if data.company.upper() == "KW" else UnitOfPower.WATT


@dataclass(frozen=True, kw_only=True)
class HypontechSensorDescription(SensorEntityDescription):
    """Describes Hypontech overview sensor entity."""

    value_fn: Callable[[OverviewData], float | None]
    unit_fn: Callable[[OverviewData], str] | None = None


@dataclass(frozen=True, kw_only=True)
class HypontechPlantSensorDescription(SensorEntityDescription):
    """Describes Hypontech plant sensor entity."""

    value_fn: Callable[[HypontechPlant], float | None]
    unit_fn: Callable[[HypontechPlant], str] | None = None


OVERVIEW_SENSORS: tuple[HypontechSensorDescription, ...] = (
    HypontechSensorDescription(
        key="pv_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: c.power,
        unit_fn=_power_unit,
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

PLANT_SENSORS: tuple[HypontechPlantSensorDescription, ...] = (
    # Historically keyed "pv_power" when total power was the only reading (no
    # battery support). Now it carries the PV-only power from the monitor
    # endpoint; the plant endpoint's total power is exposed as "total_power".
    HypontechPlantSensorDescription(
        key="pv_power",
        translation_key="pv_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: c.monitor.power_pv,
    ),
    HypontechPlantSensorDescription(
        key="total_power",
        translation_key="total_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: c.info.power,
        unit_fn=lambda c: _power_unit(c.info),
    ),
    HypontechPlantSensorDescription(
        key="lifetime_energy",
        translation_key="lifetime_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda c: c.info.e_total,
    ),
    HypontechPlantSensorDescription(
        key="today_energy",
        translation_key="today_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda c: c.info.e_today,
    ),
    HypontechPlantSensorDescription(
        key="load_power",
        translation_key="load_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: c.monitor.power_load,
    ),
    HypontechPlantSensorDescription(
        key="grid_power",
        translation_key="grid_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: c.monitor.meter_power,
    ),
)

# Sensors only added for plants that have a battery (storage) system.
BATTERY_SENSORS: tuple[HypontechPlantSensorDescription, ...] = (
    HypontechPlantSensorDescription(
        key="battery_power",
        translation_key="battery_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        # Positive while the battery is discharging, negative while charging.
        value_fn=lambda c: c.monitor.w_cha,
    ),
    HypontechPlantSensorDescription(
        key="battery_state_of_charge",
        translation_key="battery_state_of_charge",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: c.monitor.soc,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HypontechConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    coordinator = config_entry.runtime_data

    entities: list[SensorEntity] = [
        HypontechOverviewSensor(coordinator, desc) for desc in OVERVIEW_SENSORS
    ]

    for plant_id, plant in coordinator.data.plants.items():
        entities.extend(
            HypontechPlantSensor(coordinator, plant_id, desc) for desc in PLANT_SENSORS
        )
        if plant.info.plant_type.endswith("Storage"):
            entities.extend(
                HypontechPlantSensor(coordinator, plant_id, desc)
                for desc in BATTERY_SENSORS
            )

    async_add_entities(entities)


class HypontechOverviewSensor(HypontechEntity, SensorEntity):
    """Class describing Hypontech overview sensor entities."""

    entity_description: HypontechSensorDescription

    def __init__(
        self,
        coordinator: HypontechDataCoordinator,
        description: HypontechSensorDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.account_id}_{description.key}"

    @property
    @override
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement."""
        if self.entity_description.unit_fn is not None:
            return self.entity_description.unit_fn(self.coordinator.data.overview)
        return super().native_unit_of_measurement

    @property
    @override
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data.overview)


class HypontechPlantSensor(HypontechPlantEntity, SensorEntity):
    """Class describing Hypontech plant sensor entities."""

    entity_description: HypontechPlantSensorDescription

    def __init__(
        self,
        coordinator: HypontechDataCoordinator,
        plant_id: str,
        description: HypontechPlantSensorDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, plant_id)
        self.entity_description = description
        self._attr_unique_id = f"{plant_id}_{description.key}"

    @property
    @override
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement."""
        if self.entity_description.unit_fn is not None:
            return self.entity_description.unit_fn(self.plant)
        return super().native_unit_of_measurement

    @property
    @override
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.plant)
