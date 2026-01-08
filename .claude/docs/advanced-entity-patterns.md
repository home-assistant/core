# Advanced Entity Patterns

Patterns for complex integrations with typed library objects and multiple data sources.

## Custom EntityDescription Fields

Extend descriptions with domain-specific callables:

```python
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.helpers.typing import StateType


@dataclass(frozen=True, kw_only=True)
class MySensorDescription(
    MyBaseDescription,
    SensorEntityDescription,
):
    """Sensor description with custom fields."""

    value_fn: Callable[[MyDataType], StateType | datetime | None]
    supported_fn: Callable[[MyCoordinator], bool] = lambda _: True
    available_fn: Callable[[MyCoordinator], bool] = lambda _: True
```

## Type-Safe Library Object Access

When accessing typed library objects, use `cast` for type safety:

```python
from typing import cast
from mylib.models import DeviceStatus, BoilerState
from mylib.const import WidgetType

# Access nested typed data with cast
value_fn=lambda data: cast(
    DeviceStatus, data[WidgetType.STATUS]
).temperature

# Check key exists before access
value_fn=lambda data: (
    cast(BoilerState, data[WidgetType.BOILER]).ready_time
    if WidgetType.BOILER in data
    else None
)

# With fallback default
value_fn=lambda data: cast(
    BoilerState,
    data.get(WidgetType.BOILER, BoilerState(status="off")),
).status
```

## Widget/Dict Access Pattern

For APIs returning dict-like structures with typed values:

```python
from mylib.models import BaseWidgetOutput

# Define value_fn signature matching the data structure
value_fn: Callable[[dict[WidgetType, BaseWidgetOutput]], StateType | None]

# In native_value, pass the correct data level
@property
def native_value(self) -> StateType | None:
    """Return the sensor value."""
    return self.entity_description.value_fn(
        self.coordinator.device.dashboard.config  # Pass the dict, not device
    )
```

## Coordinator Data vs Device Object

Choose the right pattern for your data structure:

```python
# Pattern 1: Coordinator stores data directly (simple integrations)
# coordinator.data is a dict or dataclass
value_fn: Callable[[dict[str, Any]], StateType]

@property
def native_value(self) -> StateType:
    return self.entity_description.value_fn(self.coordinator.data)


# Pattern 2: Coordinator stores device/client reference (complex integrations)
# coordinator.device is a library object with nested state
value_fn: Callable[[dict[WidgetType, BaseWidget]], StateType]

@property
def native_value(self) -> StateType:
    return self.entity_description.value_fn(
        self.coordinator.device.dashboard.config
    )
```

## Entity Subclasses for Different Data Sources

When entities need different coordinators or data access patterns:

```python
class MyBaseEntity(CoordinatorEntity[MyCoordinator]):
    """Base entity for the integration."""

    _attr_has_entity_name = True


class MyConfigEntity(MyBaseEntity):
    """Entity using config/dashboard data (real-time updates)."""

    @property
    def native_value(self) -> StateType | datetime | None:
        """Return the sensor value from dashboard config."""
        return self.entity_description.value_fn(
            self.coordinator.device.dashboard.config
        )


class MyStatisticEntity(MyBaseEntity):
    """Entity using statistics data (periodic updates)."""

    _unavailable_when_machine_off = False  # Stats available when device is off

    @property
    def native_value(self) -> StateType | None:
        """Return the sensor value from statistics."""
        return self.entity_description.value_fn(
            self.coordinator.device.statistics.widgets
        )
```

## Reusing EntityDescription Across Entity Types

When config and statistic entities share the same description structure:

```python
# Single description type for both
@dataclass(frozen=True, kw_only=True)
class MySensorDescription(LaMarzoccoEntityDescription, SensorEntityDescription):
    value_fn: Callable[[dict[WidgetType, BaseWidgetOutput]], StateType | None]

# Config sensors
CONFIG_SENSORS: tuple[MySensorDescription, ...] = (...)

# Statistic sensors (same type, different data source)
STATISTIC_SENSORS: tuple[MySensorDescription, ...] = (...)

# Different entity classes handle data access
class MyConfigSensor(MyEntity, SensorEntity):
    @property
    def native_value(self):
        return self.entity_description.value_fn(
            self.coordinator.device.dashboard.config
        )

class MyStatisticSensor(MyConfigSensor):
    _unavailable_when_machine_off = False

    @property
    def native_value(self):
        return self.entity_description.value_fn(
            self.coordinator.device.statistics.widgets
        )
```

## Availability with Machine State

Check device state for availability:

```python
from typing import cast
from mylib.const import MachineState, WidgetType
from mylib.models import MachineStatus

class MyEntity(CoordinatorEntity[MyCoordinator]):
    _unavailable_when_machine_off = True

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        if not super().available:
            return False

        # Check machine state from typed widget
        machine_state = (
            cast(
                MachineStatus,
                self.coordinator.device.dashboard.config[WidgetType.MACHINE_STATUS],
            ).status
            if WidgetType.MACHINE_STATUS in self.coordinator.device.dashboard.config
            else MachineState.OFF
        )

        if self._unavailable_when_machine_off and machine_state is MachineState.OFF:
            return False

        return True
```
