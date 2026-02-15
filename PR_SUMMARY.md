# Add Roborock Q10 Support and Upgrade to python-roborock 4.14.0

## Summary

This PR adds support for Roborock Q10 vacuum cleaners (Model B01) and upgrades the integration to use `python-roborock` version 4.14.0, which includes significant API changes and improvements for the Q10 series.

## Changes

### Core Updates
- **Upgraded dependency**: `python-roborock` from 4.12.0 to 4.14.0
- **Added Q10 support**: Full integration support for Roborock Q10 S5+ and similar B01 protocol devices
- **New coordinator**: `RoborockB01Q10UpdateCoordinator` for Q10-specific data handling

### API Compatibility Fixes
The python-roborock 4.14.0 release introduced breaking changes that required adapter updates:

1. **MQTT Architecture**: Q10 devices now use async MQTT pattern instead of synchronous polling
   - Implemented `api.start()` to initialize MQTT subscribe loop
   - Changed from `api.status.refresh()` to `api.refresh()`
   - Subscribe loop continuously receives status updates via MQTT

2. **Data Capture**: Implemented wrapper pattern to capture complete MQTT data
   - Previous version only exposed 11 filtered properties from `StatusTrait`
   - MQTT messages contain 40+ data points (battery, filter life, fault codes, brush life, etc.)
   - New wrapper intercepts raw MQTT data before filtering, ensuring all sensors have access to complete device state

3. **Enum Handling**: Added proper handling for python-roborock enums
   - `YXDeviceWorkMode` for cleaning modes
   - `YXFanLevel` for fan speed levels
   - `YXWaterLevel` for water flow control
   - Fixed typo: `YXFanLevel.QUIET` (was incorrectly `QUITE` in some contexts)

### New Features
- **Q10 Vacuum Entity**: Full vacuum control with Q10-specific features
- **Q10 Sensors**: Complete sensor coverage including:
  - Battery level
  - Filter life remaining
  - Main brush life
  - Side brush life
  - Sensor module life
  - Vacuum error codes (fault detection)
  - Cleaning statistics (area, time, count)
  - Device status and mode
- **Q10 Select Entities**: Cleaning mode, fan level, and water level controls
- **Service Actions**: Map retrieval, goto position, custom commands

### Technical Implementation

#### Coordinator Pattern
```python
# Wrapper to capture full MQTT data before StatusTrait filtering
def update_wrapper(decoded_dps: dict) -> None:
    self._last_mqtt_data.update(decoded_dps)
    original_update(decoded_dps)

self.api.status.update_from_dps = update_wrapper
```

This ensures all B01_Q10_DP enum values from MQTT are accessible to sensors, not just the 11 typed properties exposed by StatusTrait.

#### Async MQTT Flow
```python
# Start MQTT subscribe loop
await self.api.start()

# Trigger device refresh
await self.api.refresh()

# Wait for MQTT response
await asyncio.sleep(1)

# Access complete status data
data = self._last_mqtt_data.copy()
```

## Testing

- ✅ All existing Roborock tests pass
- ✅ Q10-specific tests added and passing (3/3)
- ✅ Live testing completed with real Roborock Q10 S5+ device:
  - Model: roborock.vacuum.ss07
  - Protocol: B01
  - Firmware: 03.10.92
  - All entities functional (vacuum, sensors, selects)
  - MQTT communication stable
  - All sensor data accessible (filter life, fault codes, etc.)

## Breaking Changes

None. This PR is backward compatible with existing Roborock integrations while adding new Q10 support.

## Related Issues

- Implements support for python-roborock 4.14.0 release
- Adds Q10 vacuum support requested by users

## Checklist

- [x] Code follows Home Assistant style guidelines
- [x] Tests added/updated and passing
- [x] Documentation updated where needed
- [x] Type hints added (Platinum quality scale)
- [x] Live device testing completed
- [x] No breaking changes for existing users
