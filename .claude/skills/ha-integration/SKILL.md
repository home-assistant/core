---
name: ha-integration
description: Develop Home Assistant integrations following best practices. Use when creating, modifying, or reviewing integration code including config flows, entities, coordinators, diagnostics, services, and tests.
---

# Home Assistant Integration Development

You are developing a Home Assistant integration. Follow these guidelines and reference the supporting documentation for specific components.

## Quick Reference

| Component | Reference File |
|-----------|----------------|
| Config flow | [config-flow.md](config-flow.md) |
| Data coordinator | [coordinator.md](coordinator.md) |
| Entities (base) | [entity.md](entity.md) |
| Sensors | [sensor.md](sensor.md) |
| Binary sensors | [binary-sensor.md](binary-sensor.md) |
| Switches | [switch.md](switch.md) |
| Numbers | [number.md](number.md) |
| Selects | [select.md](select.md) |
| Buttons | [button.md](button.md) |
| Device management | [device.md](device.md) |
| Diagnostics | [diagnostics.md](diagnostics.md) |
| Services | [services.md](services.md) |
| Testing | [testing.md](testing.md) |

## Integration Structure

```
homeassistant/components/my_integration/
├── __init__.py          # Entry point with async_setup_entry
├── manifest.json        # Integration metadata and dependencies
├── const.py            # Domain and constants
├── config_flow.py      # UI configuration flow
├── coordinator.py      # Data update coordinator
├── entity.py          # Base entity class
├── sensor.py          # Sensor platform
├── diagnostics.py     # Diagnostic data collection
├── strings.json        # User-facing text and translations
├── services.yaml       # Service definitions (if applicable)
└── quality_scale.yaml  # Quality scale rule status
```

## Quality Scale Levels

- **Bronze**: Basic requirements (ALL Bronze rules are mandatory)
- **Silver**: Enhanced functionality (entity unavailability, parallel updates, auth flows)
- **Gold**: Advanced features (device management, diagnostics, translations)
- **Platinum**: Highest quality (strict typing, async dependencies, websession injection)

Check `manifest.json` for `"quality_scale"` key and `quality_scale.yaml` for rule status.

## Core Patterns

### Entry Point (`__init__.py`)

```python
"""Integration for My Device."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import MyCoordinator

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]

type MyIntegrationConfigEntry = ConfigEntry[MyCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: MyIntegrationConfigEntry) -> bool:
    """Set up My Integration from a config entry."""
    coordinator = MyCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: MyIntegrationConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
```

### Constants (`const.py`)

```python
"""Constants for My Integration."""

DOMAIN = "my_integration"
```

### Manifest (`manifest.json`)

```json
{
  "domain": "my_integration",
  "name": "My Integration",
  "codeowners": ["@username"],
  "config_flow": true,
  "documentation": "https://www.home-assistant.io/integrations/my_integration",
  "integration_type": "hub",
  "iot_class": "local_polling",
  "requirements": ["my-library==1.0.0"],
  "quality_scale": "bronze"
}
```

## Python Requirements

- **Compatibility**: Python 3.13+
- **Type hints**: Required for all functions and methods
- **f-strings**: Preferred over `%` or `.format()`
- **Async**: All external I/O must be async

## Code Quality

- **Formatting**: Ruff
- **Linting**: PyLint and Ruff
- **Type Checking**: MyPy
- **Testing**: pytest with >95% coverage

## Common Anti-Patterns to Avoid

```python
# Blocking operations
data = requests.get(url)  # Use async or executor
time.sleep(5)  # Use asyncio.sleep()

# Hardcoded strings
self._attr_name = "Temperature"  # Use translation_key

# Too much in try block
try:
    data = await client.get_data()
    processed = data["value"] * 100  # Move outside try
except Error:
    pass

# User-configurable polling
vol.Optional("scan_interval"): cv.positive_int  # Not allowed
```

## Development Commands

```bash
# Run tests with coverage
pytest ./tests/components/<domain> \
  --cov=homeassistant.components.<domain> \
  --cov-report term-missing \
  --numprocesses=auto

# Type checking
mypy homeassistant/components/<domain>

# Linting
pylint homeassistant/components/<domain>

# Validate integration
python -m script.hassfest --integration-path homeassistant/components/<domain>
```
