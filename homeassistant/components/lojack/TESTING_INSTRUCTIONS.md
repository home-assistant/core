# LoJack Integration - Interactive Testing Instructions

This document provides step-by-step instructions for real-world testing of the LoJack integration before submitting to Home Assistant core.

## Prerequisites

### 1. LoJack Account Requirements
- Active LoJack/Spireon account with at least one registered vehicle
- Valid username (email) and password
- Vehicle(s) with active LoJack tracking device installed

### 2. Development Environment Setup

```bash
# Clone the repository (if not already done)
git clone https://github.com/devinslick/homeassistant-core-with-lojack.git
cd homeassistant-core-with-lojack
git checkout claude/add-lojack-integration-kurS4

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -e ".[dev]"
pip install lojack-api==0.6.3

# Or use uv for faster installation
uv pip install -r requirements_all.txt -r requirements.txt -r requirements_test.txt
```

### 3. Run Home Assistant Development Instance

```bash
# From the repository root
hass -c config

# Or use the script
python -m homeassistant -c config
```

Access Home Assistant at http://localhost:8123

---

## Test Cases

### Test 1: Initial Configuration Flow

**Objective**: Verify the config flow works correctly for first-time setup

**Steps**:
1. Navigate to Settings → Devices & Services
2. Click "+ ADD INTEGRATION"
3. Search for "LoJack"
4. Click on LoJack to start configuration
5. Enter your LoJack credentials:
   - Email: [your LoJack account email]
   - Password: [your LoJack password]
6. Click "Submit"

**Expected Results**:
- [ ] Integration appears in search results
- [ ] Configuration form shows email and password fields
- [ ] Successful authentication creates the integration
- [ ] All vehicles from your account appear as devices
- [ ] Each vehicle has a device_tracker entity

**Screenshot Locations**:
- Config flow form
- Successful setup
- Devices list

---

### Test 2: Invalid Credentials Handling

**Objective**: Verify error handling for incorrect login

**Steps**:
1. Start the configuration flow again
2. Enter incorrect credentials:
   - Email: test@invalid.com
   - Password: wrongpassword
3. Click "Submit"

**Expected Results**:
- [ ] Error message "Invalid authentication" appears
- [ ] Form remains visible for retry
- [ ] No partial config entry is created

---

### Test 3: Duplicate Account Prevention

**Objective**: Verify the same account cannot be added twice

**Steps**:
1. With the integration already configured, try adding it again
2. Enter the same credentials as the existing configuration
3. Click "Submit"

**Expected Results**:
- [ ] Abort message "This account is already configured" appears
- [ ] No duplicate entry is created

---

### Test 4: Device Tracker Entity Verification

**Objective**: Verify device tracker entities have correct attributes

**Steps**:
1. Navigate to Developer Tools → States
2. Find your vehicle's device_tracker entity (e.g., `device_tracker.2021_honda_accord`)
3. Examine the state and attributes

**Expected Attributes** (verify presence and values):
- [ ] `latitude` - Float value (e.g., 37.7749)
- [ ] `longitude` - Float value (e.g., -122.4194)
- [ ] `gps_accuracy` - Integer value in meters
- [ ] `source_type` - Should be "gps"
- [ ] `vin` - Your vehicle's VIN
- [ ] `make` - Vehicle manufacturer
- [ ] `model` - Vehicle model
- [ ] `year` - Vehicle year
- [ ] `color` - Vehicle color (if available)
- [ ] `license_plate` - License plate (if available)
- [ ] `odometer` - Mileage (if available)
- [ ] `speed` - Current speed (if moving)
- [ ] `heading` - Direction of travel (if available)
- [ ] `battery_voltage` - Vehicle battery voltage (if available)
- [ ] `address` - Human-readable location (if available)
- [ ] `timestamp` - Last update time

---

### Test 5: Location Updates

**Objective**: Verify location updates are received correctly

**Steps**:
1. Note the current latitude/longitude and timestamp of your vehicle
2. Wait 5 minutes (the default polling interval)
3. Refresh the state in Developer Tools
4. Compare the values

**Expected Results**:
- [ ] Timestamp should update (even if location hasn't changed)
- [ ] If vehicle moved, latitude/longitude should update
- [ ] No errors in Home Assistant logs

**Alternative Test** (if vehicle is moving):
1. Start tracking while someone is driving the vehicle
2. Observe location updates every 5 minutes
3. Verify position matches actual location

---

### Test 6: Device Registry Entry

**Objective**: Verify device is registered correctly

**Steps**:
1. Navigate to Settings → Devices & Services → LoJack
2. Click on your vehicle device
3. Examine device information

**Expected Results**:
- [ ] Device name is correct (e.g., "2021 Honda Accord")
- [ ] Manufacturer shows "Spireon"
- [ ] Model shows vehicle make/model
- [ ] Serial number shows VIN (if available)
- [ ] Device tracker entity is listed

---

### Test 7: Integration Reload

**Objective**: Verify integration can be reloaded without issues

**Steps**:
1. Navigate to Settings → Devices & Services → LoJack
2. Click the three-dot menu (⋮)
3. Select "Reload"
4. Wait for reload to complete

**Expected Results**:
- [ ] Integration reloads without errors
- [ ] All entities remain available
- [ ] No duplicate entities created
- [ ] Location data is refreshed

---

### Test 8: Integration Removal

**Objective**: Verify clean uninstall

**Steps**:
1. Navigate to Settings → Devices & Services → LoJack
2. Click the three-dot menu (⋮)
3. Select "Delete"
4. Confirm deletion

**Expected Results**:
- [ ] Integration is removed cleanly
- [ ] No orphan entities remain
- [ ] No errors in logs
- [ ] Can re-add integration afterward

---

### Test 9: Reauthentication Flow

**Objective**: Verify reauthentication when credentials change

**Steps**:
1. Configure the integration normally
2. Simulate authentication failure (requires changing password on LoJack account, or wait for token expiration)
3. When prompted, click "Reauthenticate"
4. Enter new password
5. Submit

**Expected Results**:
- [ ] Reauthentication form appears
- [ ] Shows current username (read-only)
- [ ] Password field is editable
- [ ] Success message after valid credentials
- [ ] Integration continues working

**Note**: This test may be difficult to trigger manually. You can verify the flow exists by checking the config_flow.py code.

---

### Test 10: Error Logging

**Objective**: Verify appropriate logging behavior

**Steps**:
1. Monitor logs during normal operation:
   ```bash
   tail -f config/home-assistant.log | grep -i lojack
   ```
2. Observe log entries during:
   - Integration setup
   - Location updates
   - Any errors

**Expected Results**:
- [ ] No errors during normal operation
- [ ] Debug messages show periodic updates
- [ ] No sensitive data (password) in logs
- [ ] Rate limiting warnings if API limits hit

---

### Test 11: Multiple Vehicles

**Objective**: Verify multiple vehicles are handled correctly (if applicable)

**Prerequisites**: LoJack account with 2+ vehicles

**Steps**:
1. Configure the integration
2. Navigate to Devices & Services → LoJack
3. Verify all vehicles appear

**Expected Results**:
- [ ] Each vehicle has its own device entry
- [ ] Each vehicle has its own device_tracker entity
- [ ] Entity names are distinct and identifiable
- [ ] All vehicles update independently

---

### Test 12: Map Integration

**Objective**: Verify vehicles appear correctly on Home Assistant map

**Steps**:
1. Navigate to the Map view in Home Assistant
2. Look for your vehicle(s)
3. Click on a vehicle marker

**Expected Results**:
- [ ] Vehicle appears on map at correct location
- [ ] Vehicle icon/marker is visible
- [ ] Clicking shows entity details
- [ ] Location updates reflected on map

---

## Automated Tests

### Running Unit Tests

```bash
# Activate virtual environment
source venv/bin/activate

# Run LoJack tests only
pytest tests/components/lojack -v

# Run with coverage
pytest tests/components/lojack --cov=homeassistant/components/lojack --cov-report=term-missing

# Update snapshots (first run only)
pytest tests/components/lojack --snapshot-update
```

**Expected Results**:
- [ ] All tests pass
- [ ] Coverage is >= 95%
- [ ] No warnings or deprecation notices

---

## Troubleshooting

### Common Issues

1. **"Cannot connect" error during setup**
   - Check internet connection
   - Verify LoJack service is not down
   - Check if API rate limiting is in effect

2. **No devices appear after setup**
   - Verify LoJack account has vehicles registered
   - Check if vehicles have active subscriptions
   - Look for errors in logs

3. **Location not updating**
   - Wait for full 5-minute interval
   - Check if vehicle LoJack device is active
   - Verify vehicle has GPS signal

4. **Entity shows "unavailable"**
   - Check integration logs for API errors
   - Try reloading the integration
   - Verify account credentials are still valid

### Log Location

```bash
# Home Assistant logs
config/home-assistant.log

# Filter for LoJack
grep -i lojack config/home-assistant.log
```

---

## Test Completion Checklist

Before submitting to core, ensure all tests pass:

| Test | Status | Notes |
|------|--------|-------|
| Test 1: Initial Configuration | ☐ | |
| Test 2: Invalid Credentials | ☐ | |
| Test 3: Duplicate Prevention | ☐ | |
| Test 4: Entity Attributes | ☐ | |
| Test 5: Location Updates | ☐ | |
| Test 6: Device Registry | ☐ | |
| Test 7: Integration Reload | ☐ | |
| Test 8: Integration Removal | ☐ | |
| Test 9: Reauthentication | ☐ | |
| Test 10: Error Logging | ☐ | |
| Test 11: Multiple Vehicles | ☐ | (if applicable) |
| Test 12: Map Integration | ☐ | |
| Automated Tests Pass | ☐ | |

---

## Reporting Issues

If you encounter any issues during testing:

1. Note the exact steps to reproduce
2. Capture relevant log entries
3. Take screenshots if helpful
4. Document expected vs actual behavior
5. Update the integration code or tests as needed

---

*Last Updated: 2026-01-31*
