"""Sensor platform for Sharp COCORO Air."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfEnergy, UnitOfPower, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SharpCocoroAirConfigEntry
from .coordinator import SharpCocoroAirCoordinator
from .entity import SharpCocoroAirEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class SharpSensorEntityDescription(SensorEntityDescription):
    """Describes a Sharp sensor entity."""

    value_fn: Callable[[dict], float | str | None]


def _prop(key: str) -> Callable[[dict], float | str | None]:
    """Return a simple property getter."""
    return lambda props: props.get(key)


def _energy_kwh(props: dict) -> float | None:
    """Convert energy from Wh to kWh."""
    wh = props.get("energy_wh")
    return round(wh / 1000.0, 3) if wh is not None else None


SENSOR_DESCRIPTIONS: tuple[SharpSensorEntityDescription, ...] = (
    SharpSensorEntityDescription(
        key="temperature",
        translation_key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=_prop("temperature_c"),
    ),
    SharpSensorEntityDescription(
        key="humidity",
        translation_key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=_prop("humidity_pct"),
    ),
    SharpSensorEntityDescription(
        key="power_consumption",
        translation_key="power_consumption",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=_prop("power_watts"),
    ),
    SharpSensorEntityDescription(
        key="energy",
        translation_key="energy",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value_fn=_energy_kwh,
    ),
    SharpSensorEntityDescription(
        key="dust",
        translation_key="dust",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_prop("dust"),
    ),
    SharpSensorEntityDescription(
        key="smell",
        translation_key="smell",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_prop("smell"),
    ),
    SharpSensorEntityDescription(
        key="pci_sensor",
        translation_key="pci_sensor",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_prop("pci_sensor"),
    ),
    SharpSensorEntityDescription(
        key="light_sensor",
        translation_key="light_sensor",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_prop("light_sensor"),
    ),
    SharpSensorEntityDescription(
        key="filter_usage",
        translation_key="filter_usage",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="h",
        value_fn=_prop("filter_usage"),
    ),
    SharpSensorEntityDescription(
        key="cleaning_mode",
        translation_key="cleaning_mode",
        value_fn=_prop("cleaning_mode"),
    ),
    SharpSensorEntityDescription(
        key="airflow",
        translation_key="airflow",
        value_fn=_prop("airflow"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SharpCocoroAirConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Sharp sensor entities."""
    coordinator = entry.runtime_data
    async_add_entities(
        SharpSensor(coordinator, device_id, description)
        for device_id in coordinator.data
        for description in SENSOR_DESCRIPTIONS
    )


class SharpSensor(SharpCocoroAirEntity, SensorEntity):
    """Sensor entity for a Sharp air purifier property."""

    entity_description: SharpSensorEntityDescription

    def __init__(
        self,
        coordinator: SharpCocoroAirCoordinator,
        device_id: str,
        description: SharpSensorEntityDescription,
    ) -> None:
        """Initialize the sensor entity."""
        super().__init__(coordinator, device_id)
        self.entity_description = description
        self._attr_unique_id = f"{device_id}_{description.key}"

    @property
    def native_value(self) -> float | str | None:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.device_properties)
