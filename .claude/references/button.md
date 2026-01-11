# Button Platform Reference

## Overview

Buttons are entities that trigger an action when pressed. They don't have a state (on/off) and are used for one-time actions like rebooting a device, triggering an update, or running a routine.

## Basic Button Implementation

```python
"""Button platform for my_integration."""
from homeassistant.components.button import ButtonEntity
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
    """Set up buttons."""
    coordinator = entry.runtime_data

    async_add_entities(
        MyButton(coordinator, device_id)
        for device_id in coordinator.data.devices
    )


class MyButton(MyEntity, ButtonEntity):
    """Representation of a button."""

    _attr_has_entity_name = True
    _attr_translation_key = "reboot"

    def __init__(self, coordinator: MyCoordinator, device_id: str) -> None:
        """Initialize the button."""
        super().__init__(coordinator, device_id)
        self._attr_unique_id = f"{device_id}_reboot"

    async def async_press(self) -> None:
        """Handle the button press."""
        await self.coordinator.client.reboot(self.device_id)
```

## Button Method

The only required method for buttons:

```python
async def async_press(self) -> None:
    """Handle the button press."""
    await self.device.trigger_action()
```

**Note**: Buttons don't have state. They only perform an action when pressed.

## Device Class

Buttons can have device classes to indicate their purpose:

```python
from homeassistant.components.button import ButtonDeviceClass

_attr_device_class = ButtonDeviceClass.RESTART
_attr_device_class = ButtonDeviceClass.UPDATE
_attr_device_class = ButtonDeviceClass.IDENTIFY
```

Device classes:
- `RESTART` - Reboot/restart device
- `UPDATE` - Trigger update check or installation
- `IDENTIFY` - Make device identify itself (blink LED, beep, etc.)

## Entity Category

Most buttons are configuration actions:

```python
from homeassistant.helpers.entity import EntityCategory

# Config buttons (device settings/actions)
_attr_entity_category = EntityCategory.CONFIG
# Examples: reboot, reset, identify

# Diagnostic buttons (troubleshooting)
_attr_entity_category = EntityCategory.DIAGNOSTIC
# Examples: test connection, refresh diagnostics
```

## Entity Descriptions Pattern

For multiple buttons:

```python
from dataclasses import dataclass
from collections.abc import Awaitable, Callable

from homeassistant.components.button import ButtonEntityDescription, ButtonDeviceClass


@dataclass(frozen=True, kw_only=True)
class MyButtonDescription(ButtonEntityDescription):
    """Describes a button."""
    press_fn: Callable[[MyClient, str], Awaitable[None]]


BUTTONS: tuple[MyButtonDescription, ...] = (
    MyButtonDescription(
        key="reboot",
        translation_key="reboot",
        device_class=ButtonDeviceClass.RESTART,
        entity_category=EntityCategory.CONFIG,
        press_fn=lambda client, device_id: client.reboot(device_id),
    ),
    MyButtonDescription(
        key="identify",
        translation_key="identify",
        device_class=ButtonDeviceClass.IDENTIFY,
        entity_category=EntityCategory.CONFIG,
        press_fn=lambda client, device_id: client.identify(device_id),
    ),
    MyButtonDescription(
        key="check_update",
        translation_key="check_update",
        device_class=ButtonDeviceClass.UPDATE,
        entity_category=EntityCategory.CONFIG,
        press_fn=lambda client, device_id: client.check_updates(device_id),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MyConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up buttons."""
    coordinator = entry.runtime_data

    async_add_entities(
        MyButton(coordinator, device_id, description)
        for device_id in coordinator.data.devices
        for description in BUTTONS
    )


class MyButton(MyEntity, ButtonEntity):
    """Button using entity description."""

    entity_description: MyButtonDescription

    def __init__(
        self,
        coordinator: MyCoordinator,
        device_id: str,
        description: MyButtonDescription,
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator, device_id)
        self.entity_description = description
        self._attr_unique_id = f"{device_id}_{description.key}"

    async def async_press(self) -> None:
        """Handle the button press."""
        await self.entity_description.press_fn(
            self.coordinator.client,
            self.device_id,
        )
```

## Common Button Types

### Restart Button

```python
class RestartButton(ButtonEntity):
    """Restart device button."""

    _attr_device_class = ButtonDeviceClass.RESTART
    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "restart"

    async def async_press(self) -> None:
        """Restart the device."""
        await self.device.restart()
```

### Update Button

```python
class UpdateButton(ButtonEntity):
    """Trigger update check button."""

    _attr_device_class = ButtonDeviceClass.UPDATE
    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "check_update"

    async def async_press(self) -> None:
        """Check for updates."""
        await self.device.check_for_updates()
```

### Identify Button

```python
class IdentifyButton(ButtonEntity):
    """Make device identify itself."""

    _attr_device_class = ButtonDeviceClass.IDENTIFY
    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "identify"

    async def async_press(self) -> None:
        """Trigger device identification."""
        await self.device.identify()
```

### Custom Action Button

```python
class CustomButton(ButtonEntity):
    """Custom action button."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "run_cycle"

    async def async_press(self) -> None:
        """Run cleaning cycle."""
        await self.device.start_cleaning_cycle()
```

## State Updates After Press

Buttons trigger coordinator refresh if needed:

```python
async def async_press(self) -> None:
    """Handle press with refresh."""
    await self.coordinator.client.reboot(self.device_id)
    # Refresh coordinator to update related entities
    await self.coordinator.async_request_refresh()
```

## Error Handling

Handle errors appropriately:

```python
from homeassistant.exceptions import HomeAssistantError


async def async_press(self) -> None:
    """Handle press with error handling."""
    try:
        await self.device.reboot()
    except DeviceOfflineError as err:
        raise HomeAssistantError(f"Device is offline: {err}") from err
    except DeviceError as err:
        raise HomeAssistantError(f"Failed to reboot: {err}") from err
```

## Testing Buttons

### Snapshot Testing

```python
"""Test buttons."""
import pytest
from syrupy import SnapshotAssertion

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_buttons(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    init_integration,
) -> None:
    """Test button entities."""
    await snapshot_platform(
        hass,
        entity_registry,
        snapshot,
        mock_config_entry.entry_id,
    )
```

### Press Testing

```python
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS


async def test_button_press(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device,
) -> None:
    """Test button press."""
    await init_integration(hass, mock_config_entry)

    # Press button
    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.my_device_reboot"},
        blocking=True,
    )

    # Verify action was called
    mock_device.reboot.assert_called_once()
```

### Error Testing

```python
async def test_button_press_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device,
) -> None:
    """Test button press with error."""
    await init_integration(hass, mock_config_entry)

    mock_device.reboot.side_effect = DeviceError("Connection failed")

    # Press button should raise error
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: "button.my_device_reboot"},
            blocking=True,
        )
```

## Common Patterns

### Pattern 1: Simple Action Button

```python
class SimpleButton(ButtonEntity):
    """Simple button that triggers action."""

    async def async_press(self) -> None:
        """Trigger action."""
        await self.device.do_something()
```

### Pattern 2: Button with Coordinator Refresh

```python
class RefreshingButton(CoordinatorEntity[MyCoordinator], ButtonEntity):
    """Button that refreshes coordinator."""

    async def async_press(self) -> None:
        """Trigger action and refresh."""
        await self.coordinator.client.action(self.device_id)
        await self.coordinator.async_request_refresh()
```

### Pattern 3: Button with Validation

```python
class ValidatingButton(ButtonEntity):
    """Button with pre-action validation."""

    async def async_press(self) -> None:
        """Validate then trigger action."""
        if not self.device.is_ready:
            raise HomeAssistantError("Device not ready")

        await self.device.trigger_action()
```

## Best Practices

### ✅ DO

- Use appropriate device class
- Set entity category (usually CONFIG)
- Handle errors with HomeAssistantError
- Implement unique IDs
- Use translation keys
- Refresh coordinator if state changes
- Provide clear button names/translations

### ❌ DON'T

- Create buttons that track state (use switch instead)
- Poll buttons (they have no state)
- Block the event loop
- Ignore errors silently
- Create buttons without entity category
- Hardcode entity names
- Use buttons for binary controls (use switch)

## Button vs. Switch vs. Service

**Use Button when**:
- One-time action with no state
- Trigger command (reboot, identify)
- User initiates action

**Use Switch when**:
- Binary control (on/off)
- State matters
- Can be turned on and off

**Use Service when**:
- Complex parameters needed
- Multiple related actions
- Integration-wide operations

## Troubleshooting

### Button Not Appearing

Check:
- [ ] Unique ID is set
- [ ] Platform is in PLATFORMS list
- [ ] Entity is added with async_add_entities
- [ ] async_press is implemented

### Button Press Not Working

Check:
- [ ] async_press is async def
- [ ] Not blocking the event loop
- [ ] API client is working
- [ ] Errors are being raised properly

### Button Not in Expected Category

Check:
- [ ] entity_category is set
- [ ] Using correct EntityCategory value
- [ ] Device class is appropriate

## Quality Scale Considerations

- **Bronze**: Unique ID required
- **Gold**: Entity translations, device class, entity category
- **Platinum**: Full type hints

## References

- [Button Documentation](https://developers.home-assistant.io/docs/core/entity/button)
- [Button Integration](https://www.home-assistant.io/integrations/button/)
