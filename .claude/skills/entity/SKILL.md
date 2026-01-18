# Entity Development

This skill covers creating and managing entities in Home Assistant integrations.

## When to Use

- Adding sensors, switches, or other entity platforms
- Understanding entity naming and unique IDs
- Implementing entity state and availability

## Unique IDs

- **Required**: Every entity must have a unique ID for registry tracking
- Must be unique per platform (not per integration)
- Don't include integration domain or platform in ID

```python
class MySensor(SensorEntity):
    def __init__(self, device_id: str) -> None:
        self._attr_unique_id = f"{device_id}_temperature"
```

**Acceptable ID Sources**:
- Device serial numbers
- MAC addresses (formatted using `format_mac` from device registry)
- Physical identifiers (printed/EEPROM)
- Config entry ID as last resort: `f"{entry.entry_id}-battery"`

**Never Use**:
- IP addresses, hostnames, URLs
- Device names
- Email addresses, usernames

## Entity Naming

Use `has_entity_name = True` for proper naming:

```python
class MySensor(SensorEntity):
    _attr_has_entity_name = True
    def __init__(self, device: Device, field: str) -> None:
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.id)},
            name=device.name,
        )
        self._attr_name = field  # e.g., "temperature", "humidity"
```

For the device itself: Set `_attr_name = None`.

## Entity Descriptions with Lambdas

When lambdas exceed line length, wrap in parentheses:

```python
SensorEntityDescription(
    key="temperature",
    name="Temperature",
    value_fn=lambda data: (  # ✅ Parenthesis on same line as lambda
        round(data["temp_value"] * 1.8 + 32, 1)
        if data.get("temp_value") is not None
        else None
    ),
)
```

## Event Lifecycle Management

Subscribe in `async_added_to_hass`:

```python
async def async_added_to_hass(self) -> None:
    """Subscribe to events."""
    self.async_on_remove(
        self.client.events.subscribe("my_event", self._handle_event)
    )
```

- Unsubscribe in `async_will_remove_from_hass` if not using `async_on_remove`
- Never subscribe in `__init__` or other methods

## State Handling

- Unknown values: Use `None` (not "unknown" or "unavailable")
- Availability: Implement `available()` property instead of using "unavailable" state

## Entity Availability

Mark entities unavailable when data cannot be fetched from device/service.

**Coordinator Pattern**:

```python
@property
def available(self) -> bool:
    """Return if entity is available."""
    return super().available and self.identifier in self.coordinator.data
```

**Direct Update Pattern**:

```python
async def async_update(self) -> None:
    """Update entity."""
    try:
        data = await self.client.get_data()
    except MyException:
        self._attr_available = False
    else:
        self._attr_available = True
        self._attr_native_value = data.value
```

## Extra State Attributes

- All attribute keys must always be present
- Unknown values: Use `None`
- Provide descriptive attributes

## Entity Categories

```python
class MySensor(SensorEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC
```

## Device Classes

Use when available:

```python
class MyTemperatureSensor(SensorEntity):
    _attr_device_class = SensorDeviceClass.TEMPERATURE
```

Provides context for: unit conversion, voice control, UI representation.

## Disabled by Default

Disable noisy or less popular entities:

```python
class MySignalStrengthSensor(SensorEntity):
    _attr_entity_registry_enabled_default = False
```

## Entity Translations

Required with `has_entity_name`. In `strings.json`:

```json
{
  "entity": {
    "sensor": {
      "phase_voltage": {
        "name": "Phase voltage"
      }
    }
  }
}
```

## Icon Translations (Gold)

**State-based Icons**:

```json
{
  "entity": {
    "sensor": {
      "tree_pollen": {
        "default": "mdi:tree",
        "state": {
          "high": "mdi:tree-outline"
        }
      }
    }
  }
}
```

**Range-based Icons** (for numeric values):

```json
{
  "entity": {
    "sensor": {
      "battery_level": {
        "default": "mdi:battery-unknown",
        "range": {
          "0": "mdi:battery-outline",
          "90": "mdi:battery-90",
          "100": "mdi:battery"
        }
      }
    }
  }
}
```

## Device Registry

Create devices and group related entities:

```python
_attr_device_info = DeviceInfo(
    connections={(CONNECTION_NETWORK_MAC, device.mac)},
    identifiers={(DOMAIN, device.id)},
    name=device.name,
    manufacturer="My Company",
    model="My Sensor",
    sw_version=device.version,
)
```

For services: Add `entry_type=DeviceEntryType.SERVICE`.

## Dynamic Device Addition

Auto-detect new devices after initial setup:

```python
def _check_device() -> None:
    current_devices = set(coordinator.data)
    new_devices = current_devices - known_devices
    if new_devices:
        known_devices.update(new_devices)
        async_add_entities([MySensor(coordinator, device_id) for device_id in new_devices])

entry.async_on_unload(coordinator.async_add_listener(_check_device))
```

## Stale Device Removal

Auto-remove when devices disappear from hub/account:

```python
device_registry.async_update_device(
    device_id=device.id,
    remove_config_entry_id=self.config_entry.entry_id,
)
```

Implement `async_remove_config_entry_device` when manual deletion is needed.

## Related Skills

- `coordinator` - Data fetching for entities
- `device-discovery` - Dynamic entity addition
- `write-tests` - Entity testing patterns
