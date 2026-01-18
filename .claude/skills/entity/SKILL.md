# Entity Development

This skill covers creating and managing entities in Home Assistant integrations.

## When to Use

- Adding sensors, switches, or other entity platforms
- Understanding entity naming and unique IDs
- Implementing entity state and availability

## Entity Structure

```python
"""Sensor platform for My Integration."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import MyIntegrationConfigEntry
from .const import DOMAIN
from .coordinator import MyCoordinator
from .entity import MyEntity

SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="temperature",
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

## Base Entity Class

Create a shared base entity in `entity.py`:

```python
"""Base entity for My Integration."""

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
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.device_id)},
            name=coordinator.device_name,
            manufacturer="My Company",
            model=coordinator.device_model,
            sw_version=coordinator.device_version,
        )
```

## Unique IDs

**Every entity must have a unique ID.**

### Acceptable Sources

- Device serial numbers
- MAC addresses (use `format_mac` from device registry)
- Physical identifiers (printed/EEPROM)
- Config entry ID as last resort: `f"{entry.entry_id}-battery"`

### Never Use

- IP addresses, hostnames, URLs
- Device names
- Email addresses, usernames

```python
# Good examples
self._attr_unique_id = f"{device.serial}_{description.key}"
self._attr_unique_id = f"{format_mac(device.mac)}_temperature"

# Bad examples
self._attr_unique_id = f"{device.ip}_sensor"  # IP can change
self._attr_unique_id = device.name  # Names can change
```

## Entity Naming

Use `has_entity_name = True` for proper naming:

```python
class MySensor(SensorEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "temperature"  # For translations

    # Or for the main device entity:
    _attr_name = None  # Entity will use device name
```

## State Handling

- Unknown values: Use `None` (not "unknown" or "unavailable")
- Use properties or `_attr_` attributes

```python
@property
def native_value(self) -> float | None:
    """Return the sensor value."""
    value = self.coordinator.data.get("temperature")
    return value if value is not None else None
```

## Entity Availability

```python
@property
def available(self) -> bool:
    """Return if entity is available."""
    return (
        super().available
        and self.entity_description.key in self.coordinator.data
    )
```

## Entity Descriptions with Lambdas

When lambdas exceed line length, wrap in parentheses:

```python
SensorEntityDescription(
    key="temperature",
    name="Temperature",
    value_fn=lambda data: (
        round(data["temp_value"] * 1.8 + 32, 1)
        if data.get("temp_value") is not None
        else None
    ),
)
```

## Event Lifecycle

Subscribe to events in `async_added_to_hass`:

```python
async def async_added_to_hass(self) -> None:
    """Subscribe to events."""
    await super().async_added_to_hass()
    self.async_on_remove(
        self.client.events.subscribe("my_event", self._handle_event)
    )
```

## Entity Categories

```python
from homeassistant.const import EntityCategory

class MyDiagnosticSensor(SensorEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC
```

## Device Classes

Always set appropriate device class when available:

```python
class MyTemperatureSensor(SensorEntity):
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT
```

## Disabled by Default

For noisy or less popular entities:

```python
class MySignalStrengthSensor(SensorEntity):
    _attr_entity_registry_enabled_default = False
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
      "battery": {
        "name": "Battery"
      }
    }
  }
}
```

## Icon Translations (Gold)

State-based icons:

```json
{
  "entity": {
    "sensor": {
      "status": {
        "default": "mdi:check",
        "state": {
          "error": "mdi:alert"
        }
      }
    }
  }
}
```

Range-based icons:

```json
{
  "entity": {
    "sensor": {
      "battery": {
        "default": "mdi:battery-unknown",
        "range": {
          "0": "mdi:battery-outline",
          "50": "mdi:battery-50",
          "100": "mdi:battery"
        }
      }
    }
  }
}
```

## Device Registry

### Full DeviceInfo Example

```python
from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    DeviceEntryType,
    DeviceInfo,
)

_attr_device_info = DeviceInfo(
    # At least one identifier required
    identifiers={(DOMAIN, device.serial)},
    # Optional: network connections for device matching
    connections={(CONNECTION_NETWORK_MAC, device.mac)},
    name=device.name,
    manufacturer="My Company",
    model="Model X",
    model_id="MX-1000",
    sw_version=device.firmware,
    hw_version=device.hardware,
    serial_number=device.serial,
    configuration_url=f"http://{device.host}",
    # For service integrations (not physical devices)
    entry_type=DeviceEntryType.SERVICE,
)
```

### Service vs Device

```python
# Physical device (default)
DeviceInfo(identifiers={(DOMAIN, serial)}, ...)

# Cloud service or API (not a physical device)
DeviceInfo(
    identifiers={(DOMAIN, account_id)},
    entry_type=DeviceEntryType.SERVICE,
    ...
)
```

## Extra State Attributes

```python
@property
def extra_state_attributes(self) -> dict[str, Any]:
    """Return extra state attributes."""
    return {
        "last_updated": self.coordinator.data.timestamp,
        "firmware_version": self.coordinator.data.firmware,
    }
```

**Rules:**
- All attribute keys must always be present
- Use `None` for unknown values
- Keep attributes minimal and useful

## Dynamic Device Management

### Adding New Devices

```python
def _check_devices() -> None:
    """Check for new devices."""
    current = set(coordinator.data.devices)
    new_devices = current - known_devices
    if new_devices:
        known_devices.update(new_devices)
        async_add_entities([
            MySensor(coordinator, device_id)
            for device_id in new_devices
        ])

entry.async_on_unload(coordinator.async_add_listener(_check_devices))
```

### Removing Stale Devices

```python
from homeassistant.helpers import device_registry as dr

device_registry = dr.async_get(hass)
device_registry.async_update_device(
    device_id=device_entry.id,
    remove_config_entry_id=entry.entry_id,
)
```

## Related Skills

- `coordinator` - Data fetching for entities
- `device-discovery` - Dynamic entity addition
- `write-tests` - Entity testing patterns
