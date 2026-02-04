# Claude Code Instructions for qube_heatpump Integration

Home Assistant integration for Qube Heat Pumps via Modbus TCP.

## Project Structure

```
homeassistant/components/qube_heatpump/
├── __init__.py          # Entry point, async_setup_entry, async_unload_entry
├── config_flow.py       # UI configuration flow with duplicate detection
├── const.py             # DOMAIN, PLATFORMS, configuration constants
├── coordinator.py       # DataUpdateCoordinator for polling
├── hub.py               # QubeHub wrapper around library's QubeClient
├── manifest.json        # Integration metadata, requirements
├── sensor.py            # Sensor entities (21 sensors + computed)
├── strings.json         # UI strings and translations
└── quality_scale.yaml   # Bronze quality scale compliance

tests/components/qube_heatpump/
├── conftest.py          # Fixtures: mock_qube_client, mock_qube_state, mock_config_entry
├── test_config_flow.py  # Config flow tests (100% coverage required)
├── test_coordinator.py  # Coordinator tests
├── test_hub.py          # Hub tests
├── test_init.py         # Setup/unload tests
└── test_sensor.py       # Sensor entity tests
```

## Key Components

### QubeHub (hub.py)
Wrapper around the `python-qube-heatpump` library's `QubeClient`:
- Manages connection with backoff logic
- Provides `async_get_all_data()` for coordinator

### QubeCoordinator (coordinator.py)
`DataUpdateCoordinator` that polls the heat pump:
- 60-second update interval
- Calls `hub.async_get_all_data()`
- Handles `UpdateFailed` exceptions

### Sensors (sensor.py)
- **QubeSensor**: Generic sensor using `QubeSensorEntityDescription`
- **QubeComputedSensor**: Status code sensor
- **QubeStandbyPowerSensor**: Static 17W standby power
- **QubeStandbyEnergySensor**: Accumulated standby energy (RestoreSensor)
- **QubeTotalEnergyIncludingStandbySensor**: Total energy including standby

### Config Flow (config_flow.py)
- User flow with connection validation
- Duplicate IP detection (resolves hostnames)
- Reconfigure flow for updating host/port

## Entity ID Naming Convention

Entity IDs use the sensor `key` (vendor_id equivalent) for stable, predictable naming.

**Pattern:** `{platform}.{device_name}_{key}`

**Examples:**
- `sensor.qube_temp_supply` (not `sensor.qube_supply_temperature_cv`)
- `sensor.qube_status_heatpump` (not `sensor.qube_heat_pump_status`)

**Implementation:** Each entity sets `_attr_suggested_object_id` to the description key or translation_key.

**Benefits:**
- Stable: Entity IDs won't change when translations are updated
- Consistent with HACS version entity IDs
- Traceable: Easy mapping from code to entity_id

## Development Commands

### Run Tests
```bash
cd /Users/matthijskeij/Github/core
source venv/bin/activate

# Run integration tests with coverage
pytest tests/components/qube_heatpump \
  --cov=homeassistant.components.qube_heatpump \
  --cov-report term-missing \
  --numprocesses=auto
```

### Linting & Validation
```bash
# Ruff linting
ruff check homeassistant/components/qube_heatpump tests/components/qube_heatpump

# Ruff formatting
ruff format homeassistant/components/qube_heatpump tests/components/qube_heatpump

# Hassfest validation
python -m script.hassfest --integration-path homeassistant/components/qube_heatpump

# MyPy type checking
mypy homeassistant/components/qube_heatpump
```

### Update Translations
```bash
python -m script.translations develop --all
```

## Library Dependency

**Library**: `python-qube-heatpump` (PyPI)
**Local repo**: `/Users/matthijskeij/Github/python-qube-heatpump`

### Testing with Local Library
```bash
pip install -e /Users/matthijskeij/Github/python-qube-heatpump
pytest tests/components/qube_heatpump -v
```

### Updating Library Version
1. Update library and publish to PyPI
2. Update `manifest.json`: `"requirements": ["python-qube-heatpump==X.Y.Z"]`
3. Run `python -m script.hassfest`

## Test Coverage

Current: **96%** (target: >95%)

| Module | Coverage |
|--------|----------|
| const.py | 100% |
| coordinator.py | 100% |
| hub.py | 98% |
| sensor.py | 97% |
| config_flow.py | 94% |
| __init__.py | 92% |

### Missing Coverage (edge cases)
- `__init__.py:42,54,66,68` - Helper function, options migration, version fallback
- `config_flow.py:43,59,138-140,166` - Address resolution edge cases, reconfigure paths
- `hub.py:72` - Backoff pass statement
- `sensor.py:323,367,377,447-448` - Null data handling, state restoration

## Quality Scale: Bronze

All bronze rules are implemented (see `quality_scale.yaml`):
- config-flow, entity-unique-id, has-entity-name
- runtime-data, test-before-configure, test-before-setup
- config-flow-test-coverage, common-modules, etc.

## Adding New Sensors

1. **Add to library** (`python-qube-heatpump`):
   - Add field to `QubeState` in `models.py`
   - Add register constant in `const.py`
   - Fetch in `get_all_data()` in `client.py`

2. **Add to integration**:
   - Add `QubeSensorEntityDescription` in `sensor.py` SENSOR_TYPES
   - Add translation in `strings.json`
   - Update mock in `tests/conftest.py` mock_qube_state fixture

3. **Test**: Run full test suite and verify coverage
