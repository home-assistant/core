# Binary Sensor Platform Reference

Binary sensors represent on/off states.

## Basic Binary Sensor

```python
"""Binary sensor platform for My Integration."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import MyIntegrationConfigEntry
from .entity import MyEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MyIntegrationConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensors from config entry."""
    coordinator = entry.runtime_data

    async_add_entities([
        DoorSensor(coordinator),
        MotionSensor(coordinator),
    ])


class DoorSensor(MyEntity, BinarySensorEntity):
    """Door open/close sensor."""

    _attr_device_class = BinarySensorDeviceClass.DOOR
    _attr_translation_key = "door"

    def __init__(self, coordinator: MyCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.client.serial_number}_door"

    @property
    def is_on(self) -> bool | None:
        """Return true if door is open."""
        return self.coordinator.data.door_open
```

## Device Classes

Common binary sensor device classes:

| Device Class | On Means | Off Means |
|--------------|----------|-----------|
| `BATTERY` | Low | Normal |
| `BATTERY_CHARGING` | Charging | Not charging |
| `CONNECTIVITY` | Connected | Disconnected |
| `DOOR` | Open | Closed |
| `GARAGE_DOOR` | Open | Closed |
| `LOCK` | Unlocked | Locked |
| `MOISTURE` | Wet | Dry |
| `MOTION` | Motion detected | Clear |
| `OCCUPANCY` | Occupied | Clear |
| `OPENING` | Open | Closed |
| `PLUG` | Plugged in | Unplugged |
| `POWER` | Power detected | No power |
| `PRESENCE` | Present | Away |
| `PROBLEM` | Problem | OK |
| `RUNNING` | Running | Not running |
| `SAFETY` | Unsafe | Safe |
| `SMOKE` | Smoke detected | Clear |
| `SOUND` | Sound detected | Clear |
| `TAMPER` | Tampering | Clear |
| `UPDATE` | Update available | Up-to-date |
| `VIBRATION` | Vibration | Clear |
| `WINDOW` | Open | Closed |

## Entity Description Pattern

```python
from dataclasses import dataclass
from collections.abc import Callable

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntityDescription,
)


@dataclass(frozen=True, kw_only=True)
class MyBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describe My binary sensor entity."""

    is_on_fn: Callable[[MyData], bool | None]


BINARY_SENSORS: tuple[MyBinarySensorEntityDescription, ...] = (
    MyBinarySensorEntityDescription(
        key="door",
        translation_key="door",
        device_class=BinarySensorDeviceClass.DOOR,
        is_on_fn=lambda data: data.door_open,
    ),
    MyBinarySensorEntityDescription(
        key="motion",
        translation_key="motion",
        device_class=BinarySensorDeviceClass.MOTION,
        is_on_fn=lambda data: data.motion_detected,
    ),
    MyBinarySensorEntityDescription(
        key="low_battery",
        translation_key="low_battery",
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda data: data.battery_level < 20 if data.battery_level else None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MyIntegrationConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensors from config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        MyBinarySensor(coordinator, description)
        for description in BINARY_SENSORS
    )


class MyBinarySensor(MyEntity, BinarySensorEntity):
    """Binary sensor using entity description."""

    entity_description: MyBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: MyCoordinator,
        description: MyBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.client.serial_number}_{description.key}"

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return self.entity_description.is_on_fn(self.coordinator.data)
```

## Connectivity Sensor

```python
class ConnectivitySensor(MyEntity, BinarySensorEntity):
    """Device connectivity sensor."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "connectivity"

    @property
    def is_on(self) -> bool:
        """Return true if device is connected."""
        return self.coordinator.data.is_connected
```

## Problem Sensor

```python
class ProblemSensor(MyEntity, BinarySensorEntity):
    """Problem indicator sensor."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "problem"

    @property
    def is_on(self) -> bool:
        """Return true if there's a problem."""
        return self.coordinator.data.has_error

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {
            "error_code": self.coordinator.data.error_code,
            "error_message": self.coordinator.data.error_message,
        }
```

## Update Available Sensor

```python
class UpdateAvailableSensor(MyEntity, BinarySensorEntity):
    """Firmware update available sensor."""

    _attr_device_class = BinarySensorDeviceClass.UPDATE
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "update_available"

    @property
    def is_on(self) -> bool:
        """Return true if an update is available."""
        return self.coordinator.data.update_available
```

## Translations

In `strings.json`:

```json
{
  "entity": {
    "binary_sensor": {
      "door": {
        "name": "Door"
      },
      "motion": {
        "name": "Motion"
      },
      "low_battery": {
        "name": "Low battery"
      },
      "connectivity": {
        "name": "Connectivity"
      }
    }
  }
}
```
