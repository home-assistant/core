# Device Management Patterns

## Device Registry

Create devices to group related entities:

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

For services, add entry type:
```python
_attr_device_info = DeviceInfo(
    identifiers={(DOMAIN, entry.entry_id)},
    name="My Service",
    entry_type=DeviceEntryType.SERVICE,
)
```

## Device Info Fields

| Field | Description | Required |
|-------|-------------|----------|
| `identifiers` | Set of (domain, id) tuples | Yes |
| `connections` | Set of (type, value) tuples | Optional |
| `name` | Device name | Yes |
| `manufacturer` | Manufacturer name | Recommended |
| `model` | Model name | Recommended |
| `sw_version` | Software/firmware version | Optional |
| `hw_version` | Hardware version | Optional |
| `serial_number` | Serial number | Optional |
| `via_device` | Parent device identifier | Optional |
| `configuration_url` | URL to device config | Optional |

## Dynamic Device Addition

Auto-detect new devices after initial setup:

```python
def _check_device() -> None:
    """Check for new devices."""
    current_devices = set(coordinator.data)
    new_devices = current_devices - known_devices
    if new_devices:
        known_devices.update(new_devices)
        async_add_entities([
            MySensor(coordinator, device_id)
            for device_id in new_devices
        ])

entry.async_on_unload(coordinator.async_add_listener(_check_device))
```

## Stale Device Removal

Auto-remove when devices disappear from hub/account:

```python
device_registry = dr.async_get(hass)
device_registry.async_update_device(
    device_id=device.id,
    remove_config_entry_id=self.config_entry.entry_id,
)
```

## Manual Device Deletion

Implement `async_remove_config_entry_device` when users should be able to manually remove devices:

```python
async def async_remove_config_entry_device(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    device_entry: DeviceEntry,
) -> bool:
    """Remove a device from the integration."""
    # Return True to allow removal, False to prevent
    device_id = next(
        identifier[1]
        for identifier in device_entry.identifiers
        if identifier[0] == DOMAIN
    )
    # Check if device is still connected
    if device_id in config_entry.runtime_data.devices:
        return False  # Don't allow removal of connected devices
    return True
```

## Via Device (Hub Relationship)

For devices connected through a hub:

```python
_attr_device_info = DeviceInfo(
    identifiers={(DOMAIN, device.id)},
    name=device.name,
    via_device=(DOMAIN, hub.id),  # Reference to parent device
)
```

## Configuration URL

Provide link to device's web interface:

```python
_attr_device_info = DeviceInfo(
    identifiers={(DOMAIN, device.id)},
    name=device.name,
    configuration_url=f"http://{device.host}",
)
```
