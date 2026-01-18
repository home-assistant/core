# Create Integration

This skill guides you through creating a new Home Assistant integration from scratch.

## When to Use

- Creating a brand new integration for a device or service
- Understanding the structure and requirements of an integration
- Setting up the foundation before adding platforms

## Standard Integration Structure

```
homeassistant/components/my_integration/
├── __init__.py          # Entry point with async_setup_entry
├── manifest.json        # Integration metadata and dependencies
├── const.py            # Domain and constants
├── config_flow.py      # UI configuration flow
├── coordinator.py      # Data update coordinator (if needed)
├── entity.py          # Base entity class (if shared patterns)
├── sensor.py          # Sensor platform (example)
├── strings.json        # User-facing text and translations
├── services.yaml       # Service definitions (if applicable)
└── quality_scale.yaml  # Quality scale rule status
```

## Step-by-Step Process

### 1. Create manifest.json

```json
{
  "domain": "my_integration",
  "name": "My Integration",
  "codeowners": ["@your_github_username"],
  "config_flow": true,
  "documentation": "https://www.home-assistant.io/integrations/my_integration",
  "integration_type": "device",
  "iot_class": "local_polling",
  "requirements": ["my-python-library==1.0.0"]
}
```

**Required fields**: `domain`, `name`, `codeowners`, `integration_type`, `documentation`

**Integration types**: `device`, `hub`, `service`, `system`, `helper`

**IoT classes**: `cloud_polling`, `cloud_push`, `local_polling`, `local_push`, `calculated`, `assumed_state`

### 2. Create const.py

```python
"""Constants for the My Integration integration."""

DOMAIN = "my_integration"
```

### 3. Create __init__.py

```python
"""The My Integration integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN

PLATFORMS: list[Platform] = [Platform.SENSOR]

type MyIntegrationConfigEntry = ConfigEntry[MyClient]


async def async_setup_entry(hass: HomeAssistant, entry: MyIntegrationConfigEntry) -> bool:
    """Set up My Integration from a config entry."""
    client = MyClient(entry.data[CONF_HOST])

    # Test connection
    try:
        await client.async_get_data()
    except MyException as err:
        raise ConfigEntryNotReady(f"Failed to connect: {err}") from err

    entry.runtime_data = client

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: MyIntegrationConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
```

### 4. Create config_flow.py

See the `config-flow` skill for detailed guidance.

### 5. Create strings.json

```json
{
  "config": {
    "step": {
      "user": {
        "data": {
          "host": "Host",
          "api_key": "API key"
        },
        "data_description": {
          "host": "Hostname or IP address of your device"
        }
      }
    },
    "error": {
      "cannot_connect": "Failed to connect",
      "invalid_auth": "Invalid authentication"
    },
    "abort": {
      "already_configured": "Device is already configured"
    }
  }
}
```

## Python Requirements

- **Compatibility**: Python 3.13+
- Use modern features: pattern matching, type hints, f-strings, dataclasses, walrus operator

## Code Style

- **Formatting**: Ruff
- **Docstrings**: Required for all functions/methods
- **File headers**: Short and concise
  ```python
  """Integration for My Device."""
  ```

## Writing Style

- Friendly and informative tone
- Use second-person ("you" and "your") for user-facing messages
- Use backticks for: file paths, filenames, variable names
- Use sentence case for titles and messages
- Avoid abbreviations

## Next Steps

After creating the basic structure:
1. Implement config flow (see `config-flow` skill)
2. Add a coordinator if needed (see `coordinator` skill)
3. Add entity platforms (see `entity` skill)
4. Write tests (see `write-tests` skill)
5. Track quality scale progress (see `quality-scale` skill)

## Related Skills

- `config-flow` - Implement configuration flows
- `coordinator` - Data update coordinator patterns
- `entity` - Entity development
- `write-tests` - Testing patterns
- `quality-scale` - Quality requirements
