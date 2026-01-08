# Skill: Add Entity

Use this skill when adding new entity types to a Home Assistant integration.

## Pre-Implementation Checklist

Before creating entities, analyze the existing integration and verify:

- [ ] **EntityCategory**: Is this `DIAGNOSTIC` (stats/health/counters) or primary (user-facing measurement)?
- [ ] **supported_fn**: Does this entity exist on all device models, or only specific ones?
- [ ] **available_fn**: When should this entity be unavailable beyond coordinator failure?
- [ ] **value_fn signature**: What data type does the lambda receive? (dict, dataclass, library object)
- [ ] **Multiple coordinators**: Does this data come from a different update source (config vs statistics)?
- [ ] **Existing patterns**: Check other entity files in the integration for established patterns

## Workflow

### Step 1: Choose entity platform

Common platforms:
- `sensor` - Read-only values (temperature, humidity, power)
- `binary_sensor` - On/off states (motion, door, connectivity)
- `switch` - Controllable on/off (outlets, toggles)
- `button` - Trigger actions (restart, identify)
- `number` - Adjustable numeric values (brightness, volume)
- `select` - Dropdown selections (modes, presets)
- `climate` - HVAC controls
- `light` - Light controls
- `cover` - Blinds, garage doors

### Step 2: Create or update platform file

Create `homeassistant/components/<domain>/<platform>.py`:

```python
"""Sensor platform for My Integration."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import MyCoordinator
from .entity import MyEntity

# Use type alias for config entry
from . import MyConfigEntry


@dataclass(frozen=True, kw_only=True)
class MySensorEntityDescription(SensorEntityDescription):
    """Describe a sensor entity."""

    value_fn: Callable[[MyData], float | None]


SENSORS: tuple[MySensorEntityDescription, ...] = (
    MySensorEntityDescription(
        key="temperature",
        translation_key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda data: data.temperature,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MyConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors from a config entry."""
    coordinator = entry.runtime_data

    async_add_entities(
        MySensor(coordinator, description)
        for description in SENSORS
    )


class MySensor(MyEntity, SensorEntity):
    """Representation of a sensor."""

    entity_description: MySensorEntityDescription

    def __init__(
        self,
        coordinator: MyCoordinator,
        description: MySensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.device_id}_{description.key}"

    @property
    def native_value(self) -> float | None:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.coordinator.data)
```

### Step 3: Create base entity class

Create `homeassistant/components/<domain>/entity.py`:

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

### Step 4: Register platform

Add to `PLATFORMS` in `__init__.py`:
```python
from homeassistant.const import Platform

PLATFORMS = [Platform.SENSOR]  # Add new platform here
```

### Step 5: Add translations

In `strings.json`:
```json
{
  "entity": {
    "sensor": {
      "temperature": {
        "name": "Temperature"
      }
    }
  }
}
```

### Step 6: Write tests

```python
@pytest.fixture
def platforms() -> list[Platform]:
    """Test sensors only."""
    return [Platform.SENSOR]

@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_sensors(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensor entities."""
    await snapshot_platform(
        hass, entity_registry, snapshot, mock_config_entry.entry_id
    )
```

### Step 7: Validate

```bash
pre-commit run --all-files
pytest ./tests/components/<domain> --cov=homeassistant.components.<domain>
python -m script.hassfest
python -m script.translations develop --all
```

## Key Reminders

- **Always use `_attr_has_entity_name = True`**
- **Set `translation_key`** for entity name translations
- **Use `device_class`** when available
- **Unique ID format**: `{device_id}_{entity_key}`
- **Coordinator pattern** for data updates

## Entity Description Pattern

For multiline value functions:
```python
MySensorEntityDescription(
    key="power",
    value_fn=lambda data: (
        round(data.power / 1000, 2)
        if data.power is not None
        else None
    ),
)
```

## Reference

- Basic patterns: `.claude/docs/entity-patterns.md`
- Advanced patterns (casting, multi-coordinator): `.claude/docs/advanced-entity-patterns.md`
