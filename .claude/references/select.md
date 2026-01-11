# Select Platform Reference

## Overview

Select entities allow users to choose from a predefined list of options. They're used for settings like operation modes, presets, input sources, or any configuration with a fixed set of choices.

## Basic Select Implementation

```python
"""Select platform for my_integration."""
from homeassistant.components.select import SelectEntity
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
    """Set up selects."""
    coordinator = entry.runtime_data

    async_add_entities(
        MySelect(coordinator, device_id)
        for device_id in coordinator.data.devices
    )


class MySelect(MyEntity, SelectEntity):
    """Representation of a select."""

    _attr_has_entity_name = True
    _attr_translation_key = "operation_mode"
    _attr_options = ["auto", "cool", "heat", "fan"]

    def __init__(self, coordinator: MyCoordinator, device_id: str) -> None:
        """Initialize the select."""
        super().__init__(coordinator, device_id)
        self._attr_unique_id = f"{device_id}_mode"

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        if device := self.coordinator.data.devices.get(self.device_id):
            return device.mode
        return None

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        await self.coordinator.client.set_mode(self.device_id, option)
        await self.coordinator.async_request_refresh()
```

## Select Properties

### Core Properties

```python
class MySelect(SelectEntity):
    """Select with all common properties."""

    # Basic identification
    _attr_has_entity_name = True
    _attr_translation_key = "preset"
    _attr_unique_id = "device_123_preset"

    # Available options (required)
    _attr_options = ["comfort", "eco", "away", "sleep"]

    # Entity category
    _attr_entity_category = EntityCategory.CONFIG

    @property
    def current_option(self) -> str | None:
        """Return current selected option."""
        return self.device.preset

    async def async_select_option(self, option: str) -> None:
        """Set the selected option."""
        await self.device.set_preset(option)
```

### Required Properties and Methods

```python
# List of available options
_attr_options = ["option1", "option2", "option3"]

# Current selected option
@property
def current_option(self) -> str | None:
    """Return the selected option."""
    return self.device.current_mode

# Or use attribute
_attr_current_option = "option1"

# Method to change option
async def async_select_option(self, option: str) -> None:
    """Change the selected option."""
    await self.device.set_option(option)
```

## Using Enums for Options

Recommended pattern for type safety:

```python
from enum import StrEnum


class OperationMode(StrEnum):
    """Operation modes."""
    AUTO = "auto"
    COOL = "cool"
    HEAT = "heat"
    FAN = "fan"


class MySelect(SelectEntity):
    """Select using enum."""

    _attr_options = [mode.value for mode in OperationMode]

    @property
    def current_option(self) -> str | None:
        """Return current mode."""
        if device := self.coordinator.data.devices.get(self.device_id):
            return device.mode
        return None

    async def async_select_option(self, option: str) -> None:
        """Set mode."""
        # Validate option is in enum
        mode = OperationMode(option)
        await self.coordinator.client.set_mode(self.device_id, mode)
        await self.coordinator.async_request_refresh()
```

## Entity Descriptions Pattern

For multiple select entities:

```python
from dataclasses import dataclass
from collections.abc import Awaitable, Callable

from homeassistant.components.select import SelectEntityDescription


@dataclass(frozen=True, kw_only=True)
class MySelectDescription(SelectEntityDescription):
    """Describes a select."""
    current_fn: Callable[[MyData], str | None]
    select_fn: Callable[[MyClient, str, str], Awaitable[None]]


SELECTS: tuple[MySelectDescription, ...] = (
    MySelectDescription(
        key="mode",
        translation_key="operation_mode",
        options=["auto", "cool", "heat", "fan"],
        entity_category=EntityCategory.CONFIG,
        current_fn=lambda data: data.mode,
        select_fn=lambda client, device_id, option: client.set_mode(device_id, option),
    ),
    MySelectDescription(
        key="preset",
        translation_key="preset",
        options=["comfort", "eco", "away", "sleep"],
        entity_category=EntityCategory.CONFIG,
        current_fn=lambda data: data.preset,
        select_fn=lambda client, device_id, option: client.set_preset(device_id, option),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MyConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up selects."""
    coordinator = entry.runtime_data

    async_add_entities(
        MySelect(coordinator, device_id, description)
        for device_id in coordinator.data.devices
        for description in SELECTS
    )


class MySelect(MyEntity, SelectEntity):
    """Select using entity description."""

    entity_description: MySelectDescription

    def __init__(
        self,
        coordinator: MyCoordinator,
        device_id: str,
        description: MySelectDescription,
    ) -> None:
        """Initialize the select."""
        super().__init__(coordinator, device_id)
        self.entity_description = description
        self._attr_unique_id = f"{device_id}_{description.key}"

    @property
    def current_option(self) -> str | None:
        """Return current option."""
        if device := self.coordinator.data.devices.get(self.device_id):
            return self.entity_description.current_fn(device)
        return None

    async def async_select_option(self, option: str) -> None:
        """Select option."""
        await self.entity_description.select_fn(
            self.coordinator.client,
            self.device_id,
            option,
        )
        await self.coordinator.async_request_refresh()
```

## Dynamic Options

If options change based on device state:

```python
class MyDynamicSelect(SelectEntity):
    """Select with dynamic options."""

    @property
    def options(self) -> list[str]:
        """Return available options based on device state."""
        if device := self.coordinator.data.devices.get(self.device_id):
            return device.available_modes
        return []

    @property
    def current_option(self) -> str | None:
        """Return current option."""
        if device := self.coordinator.data.devices.get(self.device_id):
            return device.current_mode
        return None

    async def async_select_option(self, option: str) -> None:
        """Select option."""
        await self.device.set_mode(option)
        await self.coordinator.async_request_refresh()
```

## Option Translation

Use translation keys for user-friendly option labels:

```json
// strings.json
{
  "entity": {
    "select": {
      "operation_mode": {
        "name": "Operation mode",
        "state": {
          "auto": "Automatic",
          "cool": "Cooling",
          "heat": "Heating",
          "fan": "Fan only"
        }
      }
    }
  }
}
```

```python
class MySelect(SelectEntity):
    """Select with translated options."""

    _attr_translation_key = "operation_mode"
    _attr_options = ["auto", "cool", "heat", "fan"]
```

## State Update Patterns

### Pattern 1: Optimistic Update

```python
async def async_select_option(self, option: str) -> None:
    """Select option with optimistic update."""
    # Update immediately
    self._attr_current_option = option
    self.async_write_ha_state()

    try:
        await self.device.set_option(option)
    except DeviceError:
        # Revert on error
        await self.coordinator.async_request_refresh()
        raise
```

### Pattern 2: Coordinator Refresh

```python
async def async_select_option(self, option: str) -> None:
    """Select option and refresh."""
    await self.device.set_option(option)
    # Get actual option from device
    await self.coordinator.async_request_refresh()
```

### Pattern 3: Direct State Update

```python
async def async_select_option(self, option: str) -> None:
    """Select option with direct state update."""
    actual_option = await self.device.set_option(option)
    # Device returns actual option
    self._attr_current_option = actual_option
    self.async_write_ha_state()
```

## Testing Selects

### Snapshot Testing

```python
"""Test selects."""
import pytest
from syrupy import SnapshotAssertion

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_selects(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    init_integration,
) -> None:
    """Test select entities."""
    await snapshot_platform(
        hass,
        entity_registry,
        snapshot,
        mock_config_entry.entry_id,
    )
```

### Option Selection Testing

```python
from homeassistant.const import ATTR_ENTITY_ID, ATTR_OPTION
from homeassistant.components.select import DOMAIN as SELECT_DOMAIN, SERVICE_SELECT_OPTION


async def test_select_option(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device,
) -> None:
    """Test selecting an option."""
    await init_integration(hass, mock_config_entry)

    # Check initial state
    state = hass.states.get("select.my_device_mode")
    assert state
    assert state.state == "auto"
    assert state.attributes["options"] == ["auto", "cool", "heat", "fan"]

    # Select new option
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: "select.my_device_mode",
            ATTR_OPTION: "cool",
        },
        blocking=True,
    )

    mock_device.set_mode.assert_called_once_with("cool")

    # Verify state updated
    state = hass.states.get("select.my_device_mode")
    assert state.state == "cool"
```

## Common Select Types

### Operation Mode

```python
class ModeSelect(SelectEntity):
    """Operation mode select."""

    _attr_translation_key = "operation_mode"
    _attr_options = ["auto", "cool", "heat", "fan", "dry"]
    _attr_entity_category = EntityCategory.CONFIG
```

### Preset

```python
class PresetSelect(SelectEntity):
    """Preset select."""

    _attr_translation_key = "preset"
    _attr_options = ["comfort", "eco", "away", "sleep", "boost"]
    _attr_entity_category = EntityCategory.CONFIG
```

### Input Source

```python
class InputSourceSelect(SelectEntity):
    """Input source select."""

    _attr_translation_key = "source"
    _attr_options = ["hdmi1", "hdmi2", "usb", "bluetooth", "optical"]
```

### Effect/Scene

```python
class EffectSelect(SelectEntity):
    """Light effect select."""

    _attr_translation_key = "effect"
    _attr_options = ["none", "rainbow", "pulse", "strobe", "breathe"]
```

## Best Practices

### ✅ DO

- Use enums for type safety
- Provide translation keys for options
- Validate selected options
- Implement unique IDs
- Use entity_category for config selects
- Keep option lists reasonable (<20 items)
- Use consistent option naming (lowercase, underscores)
- Provide clear option translations

### ❌ DON'T

- Accept options not in the list
- Have too many options (use input_select helper instead)
- Block the event loop
- Hardcode entity names
- Change options list arbitrarily
- Use for numeric values (use number entity)
- Use for binary choices (use switch)
- Have empty options list

## Select vs. Other Entities

**Use Select when**:
- Fixed list of text options
- Modes, presets, or settings
- 2-20 options

**Use Switch when**:
- Binary on/off control
- Only 2 states

**Use Number when**:
- Numeric range
- Continuous values

**Use Input Select when**:
- User-defined options
- Need dynamic option list
- Helper/template integration

## Troubleshooting

### Select Not Appearing

Check:
- [ ] Unique ID is set
- [ ] Platform is in PLATFORMS list
- [ ] options list is not empty
- [ ] Entity is added with async_add_entities

### Option Not Accepted

Check:
- [ ] Option is in options list (case-sensitive)
- [ ] Options list is properly formatted
- [ ] async_select_option handles the option

### Options Not Translating

Check:
- [ ] translation_key is set
- [ ] strings.json has state translations
- [ ] Option keys match exactly

## Quality Scale Considerations

- **Bronze**: Unique ID required
- **Gold**: Entity translations, entity category
- **Platinum**: Full type hints, use StrEnum for options

## References

- [Select Documentation](https://developers.home-assistant.io/docs/core/entity/select)
- [Select Integration](https://www.home-assistant.io/integrations/select/)
