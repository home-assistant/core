# Switch Platform Reference

## Overview

Switches are entities that can be turned on or off. They represent controllable devices like smart plugs, relays, or any binary control. Unlike binary sensors, switches can be controlled by the user.

## Basic Switch Implementation

```python
"""Switch platform for my_integration."""
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import MyConfigEntry
from .coordinator import MyCoordinator
from .entity import MyEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MyConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switches."""
    coordinator = entry.runtime_data

    async_add_entities(
        MySwitch(coordinator, device_id)
        for device_id in coordinator.data.devices
    )


class MySwitch(MyEntity, SwitchEntity):
    """Representation of a switch."""

    _attr_has_entity_name = True
    _attr_translation_key = "outlet"

    def __init__(self, coordinator: MyCoordinator, device_id: str) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, device_id)
        self._attr_unique_id = f"{device_id}_switch"

    @property
    def is_on(self) -> bool | None:
        """Return true if switch is on."""
        if device := self.coordinator.data.devices.get(self.device_id):
            return device.is_on
        return None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self.coordinator.client.turn_on(self.device_id)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self.coordinator.client.turn_off(self.device_id)
        await self.coordinator.async_request_refresh()
```

## Switch Properties and Methods

### Core Properties

```python
@property
def is_on(self) -> bool | None:
    """Return true if entity is on."""
    return self.device.state

# Or use attribute
_attr_is_on = True  # or False, or None
```

### Required Methods

```python
async def async_turn_on(self, **kwargs: Any) -> None:
    """Turn the entity on."""
    await self.device.turn_on()
    # Update state
    self._attr_is_on = True
    self.async_write_ha_state()

async def async_turn_off(self, **kwargs: Any) -> None:
    """Turn the entity off."""
    await self.device.turn_off()
    # Update state
    self._attr_is_on = False
    self.async_write_ha_state()
```

### Optional Toggle Method

```python
async def async_toggle(self, **kwargs: Any) -> None:
    """Toggle the entity."""
    # Only implement if device has native toggle
    await self.device.toggle()
    await self.coordinator.async_request_refresh()
```

**Note**: If `async_toggle` is not implemented, Home Assistant will use `async_turn_on`/`async_turn_off` based on current state.

## Device Class

Switches can have device classes to indicate their type:

```python
from homeassistant.components.switch import SwitchDeviceClass

_attr_device_class = SwitchDeviceClass.OUTLET
_attr_device_class = SwitchDeviceClass.SWITCH
```

Device classes:
- `OUTLET` - Smart plug/outlet
- `SWITCH` - Generic switch (default)

## State Update Patterns

### Pattern 1: Optimistic Update

For fast UI response:

```python
async def async_turn_on(self, **kwargs: Any) -> None:
    """Turn on."""
    # Update state immediately (optimistic)
    self._attr_is_on = True
    self.async_write_ha_state()

    try:
        await self.coordinator.client.turn_on(self.device_id)
    except DeviceError:
        # Revert on error
        self._attr_is_on = False
        self.async_write_ha_state()
        raise
```

### Pattern 2: Coordinator Refresh

Wait for actual state:

```python
async def async_turn_on(self, **kwargs: Any) -> None:
    """Turn on."""
    await self.coordinator.client.turn_on(self.device_id)
    # Refresh coordinator to get actual state
    await self.coordinator.async_request_refresh()
```

### Pattern 3: Push Update

For push-based systems:

```python
async def async_turn_on(self, **kwargs: Any) -> None:
    """Turn on."""
    # Command device
    await self.device.turn_on()
    # State will be updated via push event
    # No need to call async_write_ha_state()
```

## Entity Descriptions Pattern

For multiple similar switches:

```python
from dataclasses import dataclass
from collections.abc import Awaitable, Callable

from homeassistant.components.switch import SwitchEntityDescription


@dataclass(frozen=True, kw_only=True)
class MySwitchDescription(SwitchEntityDescription):
    """Describes a switch."""
    is_on_fn: Callable[[MyData], bool | None]
    turn_on_fn: Callable[[MyClient, str], Awaitable[None]]
    turn_off_fn: Callable[[MyClient, str], Awaitable[None]]


SWITCHES: tuple[MySwitchDescription, ...] = (
    MySwitchDescription(
        key="outlet",
        translation_key="outlet",
        device_class=SwitchDeviceClass.OUTLET,
        is_on_fn=lambda data: data.outlet_state,
        turn_on_fn=lambda client, device_id: client.turn_on_outlet(device_id),
        turn_off_fn=lambda client, device_id: client.turn_off_outlet(device_id),
    ),
    MySwitchDescription(
        key="led",
        translation_key="led",
        entity_category=EntityCategory.CONFIG,
        is_on_fn=lambda data: data.led_enabled,
        turn_on_fn=lambda client, device_id: client.enable_led(device_id),
        turn_off_fn=lambda client, device_id: client.disable_led(device_id),
    ),
)


class MySwitch(MyEntity, SwitchEntity):
    """Switch using entity description."""

    entity_description: MySwitchDescription

    def __init__(
        self,
        coordinator: MyCoordinator,
        device_id: str,
        description: MySwitchDescription,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, device_id)
        self.entity_description = description
        self._attr_unique_id = f"{device_id}_{description.key}"

    @property
    def is_on(self) -> bool | None:
        """Return if switch is on."""
        if device := self.coordinator.data.devices.get(self.device_id):
            return self.entity_description.is_on_fn(device)
        return None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on."""
        await self.entity_description.turn_on_fn(
            self.coordinator.client,
            self.device_id,
        )
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off."""
        await self.entity_description.turn_off_fn(
            self.coordinator.client,
            self.device_id,
        )
        await self.coordinator.async_request_refresh()
```

## Configuration Switches

Switches that control device settings (not physical devices):

```python
from homeassistant.helpers.entity import EntityCategory

class MyConfigSwitch(SwitchEntity):
    """Configuration switch."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "led_indicator"

    @property
    def is_on(self) -> bool:
        """Return if LED is enabled."""
        return self.device.led_enabled

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable LED indicator."""
        await self.device.set_led(True)
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable LED indicator."""
        await self.device.set_led(False)
        self._attr_is_on = False
        self.async_write_ha_state()
```

## Error Handling

Handle errors gracefully:

```python
async def async_turn_on(self, **kwargs: Any) -> None:
    """Turn on with error handling."""
    try:
        await self.device.turn_on()
    except DeviceOfflineError as err:
        # Let entity become unavailable
        raise HomeAssistantError(f"Device is offline: {err}") from err
    except DeviceError as err:
        # Specific error
        raise HomeAssistantError(f"Failed to turn on: {err}") from err
    else:
        self._attr_is_on = True
        self.async_write_ha_state()
```

## Testing Switches

### Snapshot Testing

```python
"""Test switches."""
import pytest
from syrupy import SnapshotAssertion

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_switches(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    init_integration,
) -> None:
    """Test switch entities."""
    await snapshot_platform(
        hass,
        entity_registry,
        snapshot,
        mock_config_entry.entry_id,
    )
```

### Control Testing

```python
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN


async def test_switch_on_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device,
) -> None:
    """Test turning switch on and off."""
    await init_integration(hass, mock_config_entry)

    # Test initial state
    state = hass.states.get("switch.my_device_outlet")
    assert state
    assert state.state == "off"

    # Turn on
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.my_device_outlet"},
        blocking=True,
    )
    mock_device.turn_on.assert_called_once()

    # Check state updated
    state = hass.states.get("switch.my_device_outlet")
    assert state.state == "on"

    # Turn off
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.my_device_outlet"},
        blocking=True,
    )
    mock_device.turn_off.assert_called_once()

    state = hass.states.get("switch.my_device_outlet")
    assert state.state == "off"
```

## Common Patterns

### Pattern 1: Coordinator-Based Switch

```python
class MySwitch(CoordinatorEntity[MyCoordinator], SwitchEntity):
    """Coordinator-based switch."""

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on."""
        await self.coordinator.client.turn_on(self.device_id)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off."""
        await self.coordinator.client.turn_off(self.device_id)
        await self.coordinator.async_request_refresh()

    @property
    def is_on(self) -> bool | None:
        """Return if switch is on."""
        if device := self.coordinator.data.devices.get(self.device_id):
            return device.is_on
        return None
```

### Pattern 2: Local State Management

```python
class MyLocalSwitch(SwitchEntity):
    """Switch with local state."""

    _attr_should_poll = False
    _attr_is_on = False

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on."""
        await self.device.turn_on()
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off."""
        await self.device.turn_off()
        self._attr_is_on = False
        self.async_write_ha_state()
```

### Pattern 3: With Additional Control

```python
class MyAdvancedSwitch(SwitchEntity):
    """Switch with timer support."""

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on with optional duration."""
        duration = kwargs.get("duration")  # Custom kwarg

        if duration:
            await self.device.turn_on_for(duration)
        else:
            await self.device.turn_on()

        await self.coordinator.async_request_refresh()
```

## Best Practices

### ✅ DO

- Implement both turn_on and turn_off
- Update state after commands
- Handle errors properly
- Use coordinator for state management
- Implement unique IDs
- Use translation keys
- Mark config switches with entity_category
- Refresh coordinator after commands

### ❌ DON'T

- Block the event loop
- Ignore errors silently
- Create switches without unique IDs
- Mix control and sensing (use separate entities)
- Poll unnecessarily
- Hardcode entity names
- Forget to update state after commands

## Troubleshooting

### Switch Not Responding

Check:
- [ ] turn_on/turn_off methods are async
- [ ] Not blocking the event loop
- [ ] API client is working
- [ ] Errors are being raised properly

### State Not Updating

Check:
- [ ] async_write_ha_state() is called
- [ ] Coordinator refresh is working
- [ ] is_on returns correct value
- [ ] Push updates are subscribed

### Switch Appearing as Unavailable

Check:
- [ ] Device connection is working
- [ ] Coordinator update is successful
- [ ] available property returns True
- [ ] Entity is in coordinator.data

## Quality Scale Considerations

- **Bronze**: Unique ID required
- **Gold**: Entity translations, device class (if applicable)
- **Platinum**: Full type hints

## References

- [Switch Documentation](https://developers.home-assistant.io/docs/core/entity/switch)
- [Switch Integration](https://www.home-assistant.io/integrations/switch/)
