# Device Management Reference

Device management groups entities and provides device information.

## Device Info

```python
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN


class MyEntity(CoordinatorEntity[MyCoordinator]):
    """Base entity with device info."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: MyCoordinator) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.client.serial_number)},
            name=coordinator.client.name,
            manufacturer="My Company",
            model=coordinator.client.model,
            sw_version=coordinator.client.firmware_version,
            hw_version=coordinator.client.hardware_version,
        )
```

## DeviceInfo Fields

| Field | Description | Example |
|-------|-------------|---------|
| `identifiers` | Set of (domain, id) tuples | `{(DOMAIN, "ABC123")}` |
| `connections` | Set of (type, id) tuples | `{(CONNECTION_NETWORK_MAC, mac)}` |
| `name` | Device name | `"Living Room Thermostat"` |
| `manufacturer` | Manufacturer name | `"My Company"` |
| `model` | Model name | `"Smart Thermostat v2"` |
| `model_id` | Model identifier | `"THM-2000"` |
| `sw_version` | Software/firmware version | `"1.2.3"` |
| `hw_version` | Hardware version | `"rev2"` |
| `serial_number` | Serial number | `"ABC123456"` |
| `configuration_url` | Device config URL | `"http://192.168.1.100"` |
| `suggested_area` | Suggested room/area | `"Living Room"` |
| `entry_type` | Device entry type | `DeviceEntryType.SERVICE` |
| `via_device` | Parent device identifiers | `(DOMAIN, "hub_id")` |

## Device with Connections

Use connections (like MAC address) for better device merging:

```python
from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    DeviceInfo,
    format_mac,
)


def __init__(self, coordinator: MyCoordinator) -> None:
    """Initialize the entity."""
    super().__init__(coordinator)
    self._attr_device_info = DeviceInfo(
        connections={(CONNECTION_NETWORK_MAC, format_mac(coordinator.client.mac))},
        identifiers={(DOMAIN, coordinator.client.serial_number)},
        name=coordinator.client.name,
        manufacturer="My Company",
        model=coordinator.client.model,
    )
```

## Hub and Child Devices

```python
# Hub device
class HubEntity(CoordinatorEntity[MyCoordinator]):
    """Hub entity."""

    def __init__(self, coordinator: MyCoordinator) -> None:
        """Initialize the hub entity."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.hub_id)},
            name="My Hub",
            manufacturer="My Company",
            model="Hub Pro",
        )


# Child device connected via hub
class ChildEntity(CoordinatorEntity[MyCoordinator]):
    """Child device entity."""

    def __init__(self, coordinator: MyCoordinator, device: ChildDevice) -> None:
        """Initialize the child entity."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.id)},
            name=device.name,
            manufacturer="My Company",
            model=device.model,
            via_device=(DOMAIN, coordinator.hub_id),  # Links to parent hub
        )
```

## Service Entry Type

For cloud services without physical devices:

```python
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo


self._attr_device_info = DeviceInfo(
    identifiers={(DOMAIN, entry.entry_id)},
    name="My Cloud Service",
    manufacturer="My Company",
    entry_type=DeviceEntryType.SERVICE,
)
```

## Dynamic Device Addition

Auto-detect new devices after initial setup:

```python
async def async_setup_entry(
    hass: HomeAssistant,
    entry: MyIntegrationConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors from config entry."""
    coordinator = entry.runtime_data
    known_devices: set[str] = set()

    @callback
    def _check_devices() -> None:
        """Check for new devices."""
        current_devices = set(coordinator.data.devices.keys())
        new_devices = current_devices - known_devices

        if new_devices:
            known_devices.update(new_devices)
            async_add_entities(
                MySensor(coordinator, device_id)
                for device_id in new_devices
            )

    # Initial setup
    _check_devices()

    # Listen for updates
    entry.async_on_unload(coordinator.async_add_listener(_check_devices))
```

## Stale Device Removal

Remove devices when they disappear:

```python
async def _async_update_data(self) -> MyData:
    """Fetch data and handle device removal."""
    data = await self.client.get_data()

    # Check for removed devices
    device_registry = dr.async_get(self.hass)
    current_device_ids = set(data.devices.keys())

    for device_entry in dr.async_entries_for_config_entry(
        device_registry, self.config_entry.entry_id
    ):
        # Get device ID from identifiers
        device_id = next(
            (id for domain, id in device_entry.identifiers if domain == DOMAIN),
            None,
        )

        if device_id and device_id not in current_device_ids:
            # Device no longer exists, remove it
            device_registry.async_update_device(
                device_entry.id,
                remove_config_entry_id=self.config_entry.entry_id,
            )

    return data
```

## Manual Device Removal

Allow users to manually remove devices:

```python
# In __init__.py

async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: MyIntegrationConfigEntry, device_entry: dr.DeviceEntry
) -> bool:
    """Remove a config entry from a device."""
    # Get device ID from identifiers
    device_id = next(
        (id for domain, id in device_entry.identifiers if domain == DOMAIN),
        None,
    )

    if device_id is None:
        return False

    # Check if device is still present (don't allow removal of active devices)
    coordinator = config_entry.runtime_data
    if device_id in coordinator.data.devices:
        return False  # Device still exists, can't remove

    return True  # Allow removal of stale device
```

## Device Registry Access

```python
from homeassistant.helpers import device_registry as dr


# Get device registry
device_registry = dr.async_get(hass)

# Get device by identifiers
device = device_registry.async_get_device(
    identifiers={(DOMAIN, device_id)}
)

# Get all devices for config entry
devices = dr.async_entries_for_config_entry(
    device_registry, entry.entry_id
)

# Update device
device_registry.async_update_device(
    device.id,
    sw_version="2.0.0",
)
```

## Quality Scale Requirements

- **Bronze**: No specific device requirements
- **Gold**: Devices rule - group entities under devices
- **Gold**: Stale device removal - auto-remove disconnected devices
- **Gold**: Dynamic device addition - detect new devices at runtime
