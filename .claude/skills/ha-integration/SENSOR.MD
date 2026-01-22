# Sensor Platform Reference

Sensors represent read-only values from devices.

## Basic Sensor

```python
"""Sensor platform for My Integration."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import MyIntegrationConfigEntry
from .entity import MyEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MyIntegrationConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors from config entry."""
    coordinator = entry.runtime_data

    async_add_entities([
        TemperatureSensor(coordinator),
        HumiditySensor(coordinator),
    ])


class TemperatureSensor(MyEntity, SensorEntity):
    """Temperature sensor."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_translation_key = "temperature"

    def __init__(self, coordinator: MyCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.client.serial_number}_temperature"

    @property
    def native_value(self) -> float | None:
        """Return the temperature."""
        return self.coordinator.data.temperature
```

## Device Classes

Common sensor device classes:

| Device Class | Unit Examples | Use Case |
|--------------|---------------|----------|
| `TEMPERATURE` | °C, °F | Temperature readings |
| `HUMIDITY` | % | Humidity levels |
| `PRESSURE` | hPa, mbar | Atmospheric pressure |
| `BATTERY` | % | Battery level |
| `POWER` | W, kW | Power consumption |
| `ENERGY` | Wh, kWh | Energy usage |
| `VOLTAGE` | V | Electrical voltage |
| `CURRENT` | A, mA | Electrical current |
| `CO2` | ppm | Carbon dioxide |
| `PM25` | µg/m³ | Particulate matter |

## State Classes

```python
from homeassistant.components.sensor import SensorStateClass

# For instantaneous values that can go up or down
_attr_state_class = SensorStateClass.MEASUREMENT

# For ever-increasing totals (like energy consumption)
_attr_state_class = SensorStateClass.TOTAL

# For totals that reset periodically
_attr_state_class = SensorStateClass.TOTAL_INCREASING
```

## Entity Description Pattern

For multiple sensors with similar structure:

```python
from dataclasses import dataclass
from collections.abc import Callable
from typing import Any

from homeassistant.components.sensor import SensorEntityDescription


@dataclass(frozen=True, kw_only=True)
class MySensorEntityDescription(SensorEntityDescription):
    """Describe My sensor entity."""

    value_fn: Callable[[MyData], Any]


SENSORS: tuple[MySensorEntityDescription, ...] = (
    MySensorEntityDescription(
        key="temperature",
        translation_key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.temperature,
    ),
    MySensorEntityDescription(
        key="humidity",
        translation_key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.humidity,
    ),
    MySensorEntityDescription(
        key="signal_strength",
        translation_key="signal_strength",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,  # Disabled by default
        value_fn=lambda data: data.rssi,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MyIntegrationConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors from config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        MySensor(coordinator, description)
        for description in SENSORS
    )


class MySensor(MyEntity, SensorEntity):
    """Sensor using entity description."""

    entity_description: MySensorEntityDescription

    def __init__(
        self,
        coordinator: MyCoordinator,
        description: MySensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.client.serial_number}_{description.key}"

    @property
    def native_value(self) -> StateType:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.coordinator.data)
```

## Suggested Display Precision

```python
# Control decimal places shown in UI
_attr_suggested_display_precision = 1  # Show 21.5 instead of 21.456789
```

## Timestamp Sensors

```python
from datetime import datetime

from homeassistant.components.sensor import SensorDeviceClass


class LastUpdatedSensor(MyEntity, SensorEntity):
    """Last updated timestamp sensor."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_translation_key = "last_updated"

    @property
    def native_value(self) -> datetime | None:
        """Return the last update timestamp."""
        return self.coordinator.data.last_updated
```

## Enum Sensors

```python
from homeassistant.components.sensor import SensorDeviceClass


class StatusSensor(MyEntity, SensorEntity):
    """Status sensor with enum values."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["idle", "running", "error", "offline"]
    _attr_translation_key = "status"

    @property
    def native_value(self) -> str | None:
        """Return the current status."""
        return self.coordinator.data.status
```

With translations in `strings.json`:

```json
{
  "entity": {
    "sensor": {
      "status": {
        "name": "Status",
        "state": {
          "idle": "Idle",
          "running": "Running",
          "error": "Error",
          "offline": "Offline"
        }
      }
    }
  }
}
```

## Dynamic Icons

In `strings.json`:

```json
{
  "entity": {
    "sensor": {
      "battery_level": {
        "name": "Battery level",
        "default": "mdi:battery-unknown",
        "range": {
          "0": "mdi:battery-outline",
          "10": "mdi:battery-10",
          "50": "mdi:battery-50",
          "90": "mdi:battery-90",
          "100": "mdi:battery"
        }
      }
    }
  }
}
```

## PARALLEL_UPDATES

```python
# At module level - limit concurrent updates
PARALLEL_UPDATES = 1  # Serialize to prevent overwhelming device

# Or unlimited for coordinator-based platforms
PARALLEL_UPDATES = 0
```
