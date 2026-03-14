# Agents Instructions for qube_heatpump Integration

## Overview

Home Assistant integration for Qube Heat Pumps. Communicates via Modbus TCP using the `python-qube-heatpump` library.

## Quick Reference

| Item | Location |
|------|----------|
| Integration code | `homeassistant/components/qube_heatpump/` |
| Tests | `tests/components/qube_heatpump/` |
| Library dependency | `python-qube-heatpump==1.2.3` |
| Library local repo | `/Users/matthijskeij/Github/python-qube-heatpump` |
| Quality scale | Bronze |
| Test coverage | 96% |

## Current State

**PR**: https://github.com/home-assistant/core/pull/160409
**Branch**: `add-qube-heatpump`
**Status**: Open, awaiting review

## Files Overview

| File | Purpose |
|------|---------|
| `__init__.py` | Setup/unload entry, QubeData runtime data |
| `config_flow.py` | User config flow, reconfigure, duplicate detection |
| `coordinator.py` | DataUpdateCoordinator (60s polling) |
| `hub.py` | QubeHub wrapping library QubeClient |
| `sensor.py` | 21 sensor entities + 3 computed sensors |
| `const.py` | DOMAIN, PLATFORMS, config keys |
| `strings.json` | UI translations |
| `manifest.json` | Metadata, requirements |
| `quality_scale.yaml` | Bronze compliance tracking |

## Testing

```bash
# Quick test run
source venv/bin/activate
pytest tests/components/qube_heatpump -q

# Full test with coverage
pytest tests/components/qube_heatpump \
  --cov=homeassistant.components.qube_heatpump \
  --cov-report term-missing \
  --numprocesses=auto

# Test with local library changes
pip install -e /Users/matthijskeij/Github/python-qube-heatpump
pytest tests/components/qube_heatpump -v
```

## Validation Commands

```bash
# All must pass before PR
ruff check homeassistant/components/qube_heatpump tests/components/qube_heatpump
ruff format --check homeassistant/components/qube_heatpump tests/components/qube_heatpump
python -m script.hassfest --integration-path homeassistant/components/qube_heatpump
```

## Sensor Entities

### Temperature Sensors
- `temp_supply` - Aanvoertemperatuur CV
- `temp_return` - Retourtemperatuur CV
- `temp_source_in` - Temperatuur bron vanaf dak
- `temp_source_out` - Temperatuur bron naar dak
- `temp_room` - Ruimtetemperatuur
- `temp_dhw` - Tapwatertemperatuur
- `temp_outside` - Buitentemperatuur

### Power/Energy Sensors
- `power_thermic` - Actueel Vermogen
- `power_electric` - Totaal elektrisch vermogen
- `energy_total_electric` - Totaal elektrisch verbruik
- `energy_total_thermic` - Totaal thermische opbrengst
- `cop_calc` - COP (berekend)

### Operation Sensors
- `compressor_speed` - Actuele snelheid compressor
- `flow_rate` - Gemeten Flow
- `status_code` - Heat pump status (computed)

### Setpoint Sensors
- `setpoint_room_heat_day/night` - CV setpoints
- `setpoint_room_cool_day/night` - Cooling setpoints

### Computed Sensors
- `standby_power` - Static 17W
- `standby_energy` - Accumulated (RestoreSensor)
- `total_energy_incl_standby` - Total with standby

## Mock Fixtures (conftest.py)

- `mock_qube_state` - QubeState with all 21 fields populated
- `mock_qube_client` - Mocked QubeClient with async methods
- `mock_config_entry` - MockConfigEntry for testing
- `mock_setup_entry` - Bypass actual setup for config flow tests

## Common Tasks

### Fix formatting issues
```bash
ruff format homeassistant/components/qube_heatpump tests/components/qube_heatpump
```

### Update after library changes
```bash
# Update manifest.json with new version
# Then regenerate requirements
python -m script.hassfest
```

### Run specific test file
```bash
pytest tests/components/qube_heatpump/test_sensor.py -v
```

## PR Checklist

- [x] Tests pass (47/47)
- [x] Coverage >95% (96%)
- [x] Ruff clean
- [x] Hassfest valid
- [x] Quality scale bronze complete
- [ ] Library published to PyPI (v1.2.3)
- [ ] CI passes on GitHub
