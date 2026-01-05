# Translation Patterns

## Entity Translations

Required with `has_entity_name` for international users:

```python
class MySensor(SensorEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "phase_voltage"
```

In `strings.json`:
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

## State Translations

For entities with enumerated states:

```json
{
  "entity": {
    "sensor": {
      "status": {
        "name": "Status",
        "state": {
          "idle": "Idle",
          "running": "Running",
          "error": "Error"
        }
      }
    }
  }
}
```

## Exception Translations (Gold)

Use translation keys for user-facing exceptions:

```python
raise ServiceValidationError(
    translation_domain=DOMAIN,
    translation_key="end_date_before_start_date",
)
```

In `strings.json`:
```json
{
  "exceptions": {
    "end_date_before_start_date": {
      "message": "The end date cannot be before the start date."
    }
  }
}
```

With placeholders:
```python
raise ServiceValidationError(
    translation_domain=DOMAIN,
    translation_key="invalid_value",
    translation_placeholders={"value": str(value), "min": "0", "max": "100"},
)
```

```json
{
  "exceptions": {
    "invalid_value": {
      "message": "The value {value} is invalid. Must be between {min} and {max}."
    }
  }
}
```

## Icon Translations (Gold)

### State-based Icons

```json
{
  "entity": {
    "sensor": {
      "tree_pollen": {
        "default": "mdi:tree",
        "state": {
          "low": "mdi:tree",
          "medium": "mdi:tree",
          "high": "mdi:tree-outline"
        }
      }
    }
  }
}
```

### Range-based Icons (numeric values)

```json
{
  "entity": {
    "sensor": {
      "battery_level": {
        "default": "mdi:battery-unknown",
        "range": {
          "0": "mdi:battery-outline",
          "10": "mdi:battery-10",
          "20": "mdi:battery-20",
          "30": "mdi:battery-30",
          "40": "mdi:battery-40",
          "50": "mdi:battery-50",
          "60": "mdi:battery-60",
          "70": "mdi:battery-70",
          "80": "mdi:battery-80",
          "90": "mdi:battery-90",
          "100": "mdi:battery"
        }
      }
    }
  }
}
```

## Config Flow Translations

```json
{
  "config": {
    "step": {
      "user": {
        "title": "Connect to device",
        "description": "Enter the connection details for your device.",
        "data": {
          "host": "Host",
          "api_key": "API key"
        },
        "data_description": {
          "host": "The IP address or hostname of your device",
          "api_key": "Found in the device settings"
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

## Options Flow Translations

```json
{
  "options": {
    "step": {
      "init": {
        "title": "Options",
        "data": {
          "scan_interval": "Update interval"
        }
      }
    }
  }
}
```

## Service Translations

In `services.yaml` (auto-translated from strings.json):
```yaml
my_service:
  name: My service
  description: Does something useful
  fields:
    parameter:
      name: Parameter
      description: The parameter to use
```

## Update Translations Command

After modifying `strings.json`:
```bash
python -m script.translations develop --all
```
