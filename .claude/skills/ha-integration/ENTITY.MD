# Entity Development Reference

Base patterns for entity development in Home Assistant.

## Base Entity Class

Create a shared base class to reduce duplication:

```python
"""Base entity for My Integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MyCoordinator


class MyEntity(CoordinatorEntity[MyCoordinator]):
    """Base entity for My Integration."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: MyCoordinator) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._attr_device_info = coordinator.device_info
```

## Unique IDs

Every entity must have a unique ID:

```python
class MySensor(MyEntity, SensorEntity):
    """Sensor entity."""

    def __init__(self, coordinator: MyCoordinator, sensor_type: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        # Unique per platform, don't include domain or platform name
        self._attr_unique_id = f"{coordinator.client.serial_number}_{sensor_type}"
```

**Acceptable unique ID sources:**
- Device serial numbers
- MAC addresses (use `format_mac` from device registry)
- Physical identifiers

**Never use:**
- IP addresses, hostnames, URLs
- Device names
- Email addresses, usernames

## Entity Naming

```python
class MySensor(MyEntity, SensorEntity):
    """Sensor with proper naming."""

    _attr_has_entity_name = True
    _attr_translation_key = "temperature"  # Translatable name

    def __init__(self, coordinator: MyCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        # For the main/primary entity of a device, use None
        # self._attr_name = None

        # For secondary entities, set the name
        self._attr_name = "Temperature"  # Or use translation_key
```

## Entity Translations

In `strings.json`:

```json
{
  "entity": {
    "sensor": {
      "temperature": {
        "name": "Temperature"
      },
      "humidity": {
        "name": "Humidity"
      },
      "battery": {
        "name": "Battery",
        "state": {
          "charging": "Charging",
          "discharging": "Discharging"
        }
      }
    }
  }
}
```

## Entity Availability

### Coordinator Pattern

```python
@property
def available(self) -> bool:
    """Return if entity is available."""
    return super().available and self._sensor_key in self.coordinator.data.sensors
```

### Direct Update Pattern

```python
async def async_update(self) -> None:
    """Update entity state."""
    try:
        data = await self.client.get_data()
    except MyException:
        self._attr_available = False
        return

    self._attr_available = True
    self._attr_native_value = data.value
```

## Entity Categories

```python
from homeassistant.const import EntityCategory


class DiagnosticSensor(MyEntity, SensorEntity):
    """Diagnostic sensor (hidden by default in UI)."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC


class ConfigSwitch(MyEntity, SwitchEntity):
    """Configuration switch."""

    _attr_entity_category = EntityCategory.CONFIG
```

## Disabled by Default

For noisy or less popular entities:

```python
class SignalStrengthSensor(MyEntity, SensorEntity):
    """Signal strength sensor - disabled by default."""

    _attr_entity_registry_enabled_default = False
```

## Event Lifecycle

```python
class MyEntity(CoordinatorEntity[MyCoordinator]):
    """Entity with event subscriptions."""

    async def async_added_to_hass(self) -> None:
        """Subscribe to events when added."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.client.events.subscribe(
                "state_changed",
                self._handle_state_change,
            )
        )

    @callback
    def _handle_state_change(self, event: Event) -> None:
        """Handle state change event."""
        self._attr_native_value = event.value
        self.async_write_ha_state()
```

**Key rules:**
- Subscribe in `async_added_to_hass`
- Use `async_on_remove` for automatic cleanup
- Never subscribe in `__init__`

## State Handling

```python
@property
def native_value(self) -> StateType:
    """Return the state."""
    value = self.coordinator.data.get(self._key)
    # Use None for unknown values, never "unknown" or "unavailable" strings
    if value is None:
        return None
    return value
```

## Extra State Attributes

```python
@property
def extra_state_attributes(self) -> dict[str, Any]:
    """Return extra state attributes."""
    data = self.coordinator.data
    # All keys must always be present, use None for unknown
    return {
        "last_updated": data.last_updated,
        "error_count": data.error_count,
        "firmware": data.firmware or None,  # Never omit keys
    }
```

## Entity Descriptions Pattern

For multiple similar entities:

```python
from dataclasses import dataclass
from collections.abc import Callable

from homeassistant.components.sensor import SensorEntityDescription


@dataclass(frozen=True, kw_only=True)
class MySensorEntityDescription(SensorEntityDescription):
    """Describe My sensor entity."""

    value_fn: Callable[[MyData], StateType]


SENSOR_DESCRIPTIONS: tuple[MySensorEntityDescription, ...] = (
    MySensorEntityDescription(
        key="temperature",
        translation_key="temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.temperature,
    ),
    MySensorEntityDescription(
        key="humidity",
        translation_key="humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.humidity,
    ),
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

## Multiline Lambdas

When lambdas are too long:

```python
# Good pattern - parentheses on same line as lambda
MySensorEntityDescription(
    key="temperature",
    value_fn=lambda data: (
        round(data["temp_value"] * 1.8 + 32, 1)
        if data.get("temp_value") is not None
        else None
    ),
)
```
