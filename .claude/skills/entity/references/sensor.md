# Sensor Entity Reference

## Basic Sensor

```python
"""Sensor platform for My Integration."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import MyIntegrationConfigEntry
from .entity import MyEntity


SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="temperature",
    ),
    SensorEntityDescription(
        key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="humidity",
    ),
    SensorEntityDescription(
        key="power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="power",
    ),
    SensorEntityDescription(
        key="energy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        translation_key="energy",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MyIntegrationConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors from a config entry."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        MySensor(coordinator, description)
        for description in SENSORS
        if description.key in coordinator.data
    )


class MySensor(MyEntity, SensorEntity):
    """Representation of a sensor."""

    entity_description: SensorEntityDescription

    def __init__(
        self,
        coordinator: MyCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.device_id}_{description.key}"

    @property
    def native_value(self) -> float | None:
        """Return the sensor value."""
        return self.coordinator.data.get(self.entity_description.key)
```

## Common Device Classes

| Class | Unit Examples |
|-------|---------------|
| `TEMPERATURE` | `UnitOfTemperature.CELSIUS`, `.FAHRENHEIT` |
| `HUMIDITY` | `PERCENTAGE` |
| `PRESSURE` | `UnitOfPressure.HPA`, `.MBAR` |
| `POWER` | `UnitOfPower.WATT`, `.KILO_WATT` |
| `ENERGY` | `UnitOfEnergy.KILO_WATT_HOUR`, `.WATT_HOUR` |
| `VOLTAGE` | `UnitOfElectricPotential.VOLT` |
| `CURRENT` | `UnitOfElectricCurrent.AMPERE` |
| `BATTERY` | `PERCENTAGE` |
| `CO2` | `CONCENTRATION_PARTS_PER_MILLION` |
| `ILLUMINANCE` | `LIGHT_LUX` |
| `SIGNAL_STRENGTH` | `SIGNAL_STRENGTH_DECIBELS_MILLIWATT` |

## State Classes

| Class | Use For |
|-------|---------|
| `MEASUREMENT` | Instantaneous readings (temperature, humidity) |
| `TOTAL` | Resettable totals (rainfall today) |
| `TOTAL_INCREASING` | Monotonically increasing values (energy meter) |

## Suggested Precision

Set `suggested_display_precision` for numeric sensors:

```python
SensorEntityDescription(
    key="temperature",
    device_class=SensorDeviceClass.TEMPERATURE,
    suggested_display_precision=1,  # Show 1 decimal place
)
```

## Last Reset for TOTAL

```python
@property
def last_reset(self) -> datetime | None:
    """Return the time when the sensor was last reset."""
    return self.coordinator.data.last_reset
```
