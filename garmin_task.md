# Garmin Connect Core Integration

## Phase 1: Create `aiogarmin` Library

- [ ] Create repo `cyberjunky/aiogarmin`
- [ ] `auth.py` - login, MFA flow, token refresh
- [ ] `client.py` - async API with websession injection
- [ ] `models.py` - Pydantic response models
- [ ] Tests + publish to PyPI

## Phase 2: Core Integration

- [ ] Create `homeassistant/components/garmin_connect/`
- [ ] `manifest.json`, `__init__.py`, `config_flow.py` (with MFA)
- [ ] `coordinator.py`, `sensor.py`, `const.py`
- [ ] `strings.json`, `quality_scale.yaml`

## Phase 3: Tests & PR

- [ ] Create `tests/components/garmin_connect/`
- [ ] Submit PR to home-assistant/core
