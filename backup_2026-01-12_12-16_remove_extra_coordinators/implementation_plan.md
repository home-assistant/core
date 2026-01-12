# Address PR Review Feedback - Remove Extra Coordinators

This plan addresses joostlek's review feedback on PR #160491 to simplify the Garmin Connect integration by keeping only the `core` coordinator for the initial merge.

## User Review Required

> [!IMPORTANT]
> This will significantly reduce the number of sensors available in the initial release. All non-core sensors (activities, training, body composition, goals, gear, blood pressure, menstrual) will be removed but can be added back in future PRs.

## Proposed Changes

### Coordinator Layer

#### [MODIFY] [coordinator.py](file:///home/ron/development-home-assistant/core/homeassistant/components/garmin_connect/coordinator.py)

- **Remove** `GarminConnectCoordinators` dataclass (container for all coordinators)
- **Remove** `ActivityCoordinator`, `TrainingCoordinator`, `BodyCoordinator`, `GoalsCoordinator`, `GearCoordinator`, `BloodPressureCoordinator`, `MenstrualCoordinator` classes
- **Keep** `BaseGarminCoordinator` and `CoreCoordinator` only
- **Rename** export to `GarminConnectDataUpdateCoordinator` (following HA conventions)

```diff
-class GarminConnectCoordinators:
-    core: CoreCoordinator
-    activity: ActivityCoordinator
-    ... (7 more coordinators)
+# Only CoreCoordinator remains, renamed for clarity
+class GarminConnectDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
```

---

### Integration Setup

#### [MODIFY] [__init__.py](file:///home/ron/development-home-assistant/core/homeassistant/components/garmin_connect/__init__.py)

- Simplify to use single coordinator instead of 8
- Remove `asyncio.gather()` for parallel first refresh  
- **Fix**: Use specific exception types instead of bare `except Exception`
- **Fix**: Remove log-and-raise pattern

```diff
-from .coordinator import (
-    ActivityCoordinator,
-    BloodPressureCoordinator,
-    BodyCoordinator,
-    CoreCoordinator,
-    GarminConnectCoordinators,
-    ...
-)
+from .coordinator import GarminConnectDataUpdateCoordinator

-type GarminConnectConfigEntry = ConfigEntry[GarminConnectCoordinators]
+type GarminConnectConfigEntry = ConfigEntry[GarminConnectDataUpdateCoordinator]

# async_setup_entry simplified to single coordinator
-coordinators = GarminConnectCoordinators(
-    core=CoreCoordinator(...),
-    activity=ActivityCoordinator(...),
-    ...
-)
+coordinator = GarminConnectDataUpdateCoordinator(hass, entry, client, auth)
+await coordinator.async_config_entry_first_refresh()
```

---

### Sensor Platform

#### [DELETE] [sensor_descriptions.py](file:///home/ron/development-home-assistant/core/homeassistant/components/garmin_connect/sensor_descriptions.py)

This file will be deleted. All sensor descriptions will move to `sensor.py` following the Withings pattern.

#### [MODIFY] [sensor.py](file:///home/ron/development-home-assistant/core/homeassistant/components/garmin_connect/sensor.py)

- **Move** sensor entity description dataclass into this file
- **Move** only `CORE` sensor descriptions (steps, calories, heart rate, stress, sleep, body battery, intensity, SPO2, respiration, etc.)
- **Remove** `CoordinatorType` enum (no longer needed with single coordinator)
- **Remove** `GarminConnectGearSensor` class (gear sensors removed)
- **Simplify** `async_setup_entry` to work with single coordinator
- **Fix**: Use proper `available` property implementation per joostlek's feedback

```diff
-from .sensor_descriptions import (
-    COORDINATOR_SENSOR_MAP,
-    CoordinatorType,
-    GarminConnectSensorEntityDescription,
-)
+# Sensor descriptions now defined locally

-# Complex setup iterating over multiple coordinators
+# Simple setup with single coordinator
entities = [
    GarminConnectSensor(coordinator, description)
    for description in SENSOR_DESCRIPTIONS
]
```

---

### Services

#### [MODIFY] [services.py](file:///home/ron/development-home-assistant/core/homeassistant/components/garmin_connect/services.py)

- **Remove** or comment out gear-related services (`set_active_gear`) since gear coordinator is removed
- Keep weight-related services if core coordinator fetches weight data, otherwise remove

---

### Translations & Strings

#### [MODIFY] [strings.json](file:///home/ron/development-home-assistant/core/homeassistant/components/garmin_connect/strings.json)

- Remove translation keys for sensors that are being removed (activity, training, body, goals, gear, blood pressure, menstrual sensors)
- Keep translations for core sensors only

---

## Summary of Files Changed

| File | Action | Scope |
|------|--------|-------|
| `coordinator.py` | Modify | Remove 7 coordinator classes, keep 1 |
| `__init__.py` | Modify | Simplify setup, fix exception handling |
| `sensor_descriptions.py` | Delete | Move content to sensor.py |
| `sensor.py` | Modify | Add descriptions, simplify setup |
| `services.py` | Modify | Remove gear services |
| `strings.json` | Modify | Remove unused translations |

## Backup Location

All original files backed up to:
`/home/ron/development-home-assistant/core/backup_2026-01-12_12-16_remove_extra_coordinators/`

## Verification Plan

### Automated Tests
```bash
# Run type checking
python -m mypy homeassistant/components/garmin_connect/

# Run linting
python -m ruff check homeassistant/components/garmin_connect/

# Run tests
pytest tests/components/garmin_connect/
```

### Manual Verification
- Start Home Assistant with the integration
- Verify core sensors are created (steps, heart rate, calories, etc.)
- Confirm no errors in logs during startup and data refresh
