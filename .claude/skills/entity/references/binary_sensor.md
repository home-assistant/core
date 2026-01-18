# Binary Sensor Entity Reference

## Basic Binary Sensor

```python
"""Binary sensor platform for My Integration."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import MyIntegrationConfigEntry
from .entity import MyEntity


BINARY_SENSORS: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key="door",
        device_class=BinarySensorDeviceClass.DOOR,
        translation_key="door",
    ),
    BinarySensorEntityDescription(
        key="motion",
        device_class=BinarySensorDeviceClass.MOTION,
        translation_key="motion",
    ),
    BinarySensorEntityDescription(
        key="battery_low",
        device_class=BinarySensorDeviceClass.BATTERY,
        translation_key="battery_low",
    ),
    BinarySensorEntityDescription(
        key="connected",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        translation_key="connected",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MyIntegrationConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensors from a config entry."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        MyBinarySensor(coordinator, description)
        for description in BINARY_SENSORS
        if description.key in coordinator.data
    )


class MyBinarySensor(MyEntity, BinarySensorEntity):
    """Representation of a binary sensor."""

    entity_description: BinarySensorEntityDescription

    def __init__(
        self,
        coordinator: MyCoordinator,
        description: BinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.device_id}_{description.key}"

    @property
    def is_on(self) -> bool | None:
        """Return True if the sensor is on."""
        return self.coordinator.data.get(self.entity_description.key)
```

## Common Device Classes

| Class | On Means | Off Means |
|-------|----------|-----------|
| `BATTERY` | Low battery | Normal |
| `BATTERY_CHARGING` | Charging | Not charging |
| `CONNECTIVITY` | Connected | Disconnected |
| `DOOR` | Open | Closed |
| `GARAGE_DOOR` | Open | Closed |
| `LOCK` | Unlocked | Locked |
| `MOTION` | Motion detected | No motion |
| `OCCUPANCY` | Occupied | Empty |
| `OPENING` | Open | Closed |
| `PLUG` | Plugged in | Unplugged |
| `POWER` | Power detected | No power |
| `PRESENCE` | Present | Away |
| `PROBLEM` | Problem | OK |
| `RUNNING` | Running | Not running |
| `SAFETY` | Unsafe | Safe |
| `SMOKE` | Smoke detected | Clear |
| `SOUND` | Sound detected | Quiet |
| `UPDATE` | Update available | Up to date |
| `VIBRATION` | Vibration detected | Still |
| `WINDOW` | Open | Closed |

## Diagnostic Binary Sensors

```python
from homeassistant.const import EntityCategory

BinarySensorEntityDescription(
    key="firmware_update",
    device_class=BinarySensorDeviceClass.UPDATE,
    entity_category=EntityCategory.DIAGNOSTIC,
    translation_key="firmware_update",
)
```
