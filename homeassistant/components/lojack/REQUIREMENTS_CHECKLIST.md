# LoJack Integration Requirements and Checklist

This document outlines all requirements for submitting the LoJack integration to Home Assistant core.
Use this checklist to track progress and identify blockers before submitting a PR.

## Integration Overview

- **Domain**: `lojack`
- **Name**: LoJack
- **Integration Type**: `hub` (manages multiple devices via cloud API)
- **IoT Class**: `cloud_polling`
- **Platforms**: `device_tracker`
- **Quality Scale Target**: Bronze (minimum for core inclusion)

---

## Bronze Quality Scale Requirements (Mandatory)

### Core Requirements

- [x] **config-flow**: Integration uses config flow for setup
- [x] **unique-config-entry**: Prevents duplicate config entries (uses username as unique ID)
- [x] **test-before-configure**: Tests connection during config flow
- [x] **test-before-setup**: Tests connection during async_setup_entry
- [x] **entity-unique-id**: All entities have unique IDs (uses device_id)
- [x] **has-entity-name**: Uses `_attr_has_entity_name = True`
- [x] **runtime-data**: Uses `entry.runtime_data` (not `hass.data`)
- [x] **appropriate-polling**: Uses DataUpdateCoordinator with reasonable interval (5 minutes)
- [x] **entity-event-setup**: Event subscriptions in `async_added_to_hass()` with cleanup
- [x] **dependency-transparency**: All requirements declared in manifest.json
- [x] **common-modules**: Uses common Home Assistant modules (aiohttp, coordinator, etc.)
- [x] **action-setup**: No custom services registered (exempt)
- [x] **config-flow-test-coverage**: Config flow has 100% test coverage
- [x] **docs-high-level-description**: Integration has description (in manifest + strings.json)
- [x] **docs-installation-instructions**: Documentation URL provided in manifest
- [x] **docs-removal-instructions**: Standard removal through UI

### Documentation Requirements

- [ ] **Home Assistant Documentation**: Needs PR to home-assistant.io repository
  - Integration page at `source/_integrations/lojack.markdown`
  - Include: description, setup steps, configuration options, known limitations
  - Note: Documentation PR should be submitted alongside core PR

---

## Code Quality Requirements

### Manifest.json
- [x] `domain`: "lojack"
- [x] `name`: "LoJack"
- [x] `codeowners`: ["@devinslick"]
- [x] `config_flow`: true
- [x] `documentation`: URL to home-assistant.io (placeholder until docs PR)
- [x] `integration_type`: "hub"
- [x] `iot_class`: "cloud_polling"
- [x] `requirements`: ["lojack-api==0.7.1"] (pinned version)
- [x] `quality_scale`: "bronze"

### Python Code Standards
- [x] Python 3.13+ compatible
- [x] Type hints on all functions and methods
- [x] Docstrings on all public functions
- [x] No blocking I/O in event loop
- [x] Proper async/await usage
- [x] Lazy logging (`_LOGGER.debug("msg %s", var)`)
- [x] No hardcoded strings (uses strings.json)
- [x] Error messages without periods at end
- [x] No sensitive data in logs

### Error Handling
- [x] `ConfigEntryAuthFailed` for authentication errors
- [x] `ConfigEntryNotReady` for temporary connection issues
- [x] `UpdateFailed` for data update failures
- [x] Specific exception types (no bare `except:`)
- [x] Reauthentication flow support

### Entity Implementation
- [x] Uses `CoordinatorEntity` for automatic updates
- [x] Proper `DeviceInfo` with identifiers
- [x] `_attr_has_entity_name = True`
- [x] `_attr_unique_id` based on device physical identifier
- [x] `source_type` returns `SourceType.GPS`
- [x] Handles unavailable states gracefully

---

## Testing Requirements

### Required Test Files
- [x] `tests/components/lojack/__init__.py` - setup helper
- [x] `tests/components/lojack/conftest.py` - pytest fixtures
- [x] `tests/components/lojack/const.py` - test constants
- [x] `tests/components/lojack/test_config_flow.py` - config flow tests
- [x] `tests/components/lojack/test_init.py` - setup/unload tests
- [x] `tests/components/lojack/test_device_tracker.py` - entity tests

### Test Coverage Requirements
- [ ] Overall test coverage >= 95%
- [x] Config flow coverage = 100%
- [x] All error paths tested
- [x] Duplicate entry prevention tested
- [x] Reauthentication flow tested
- [x] Setup/unload lifecycle tested
- [x] Entity state updates tested

### Test Patterns
- [x] Uses `MockConfigEntry` from tests.common
- [x] Uses `patch` for mocking API calls
- [x] Uses `AsyncMock` for async functions
- [x] Uses snapshot testing for entity states
- [x] Does not access `hass.data` directly in tests

---

## Files Checklist

### Integration Files
- [x] `homeassistant/components/lojack/__init__.py`
- [x] `homeassistant/components/lojack/config_flow.py`
- [x] `homeassistant/components/lojack/const.py`
- [x] `homeassistant/components/lojack/coordinator.py`
- [x] `homeassistant/components/lojack/device_tracker.py`
- [x] `homeassistant/components/lojack/entity.py`
- [x] `homeassistant/components/lojack/manifest.json`
- [x] `homeassistant/components/lojack/strings.json`
- [x] `homeassistant/components/lojack/quality_scale.yaml`

### Test Files
- [x] `tests/components/lojack/__init__.py`
- [x] `tests/components/lojack/conftest.py`
- [x] `tests/components/lojack/const.py`
- [x] `tests/components/lojack/test_config_flow.py`
- [x] `tests/components/lojack/test_init.py`
- [x] `tests/components/lojack/test_device_tracker.py`
- [x] `tests/components/lojack/snapshots/*.ambr` (generated by tests)

---

## Validation Commands

Run these commands before submitting:

```bash
# Validate manifest and integration structure
python -m script.hassfest

# Run type checking
mypy homeassistant/components/lojack

# Run linting
pylint homeassistant/components/lojack
ruff check homeassistant/components/lojack

# Format code
ruff format homeassistant/components/lojack tests/components/lojack

# Run tests with coverage
pytest tests/components/lojack --cov=homeassistant/components/lojack --cov-report=term-missing

# Update requirements files (if dependencies changed)
python -m script.gen_requirements_all
```

---

## Known Blockers and Resolutions

### Resolved Issues

1. **User-configurable polling interval** (BLOCKER)
   - Original: Options flow allowed users to set poll interval
   - Resolution: Removed options flow; integration determines interval (5 minutes default)

2. **hass.data storage** (BLOCKER)
   - Original: Used `hass.data[DOMAIN][entry.entry_id]`
   - Resolution: Uses `entry.runtime_data` with typed config entry

3. **Missing type hints** (BLOCKER)
   - Original: Some functions lacked type annotations
   - Resolution: Added comprehensive type hints throughout

4. **Hardcoded entity names** (BLOCKER)
   - Original: Used hardcoded name strings
   - Resolution: Uses translation keys and `_attr_has_entity_name`

5. **Missing test coverage** (BLOCKER)
   - Original: Only 2 test files with limited coverage
   - Resolution: Complete test suite with config flow, init, and entity tests

6. **Improper exception handling** (BLOCKER)
   - Original: Some bare `except:` clauses
   - Resolution: Specific exception types with proper error mapping

7. **Entity ID generation** (MINOR)
   - Original: Custom entity_id assignment
   - Resolution: Let HA generate entity IDs from unique_id

### Pending Items

1. **Documentation PR**
   - Needs: Create PR to home-assistant.io repository
   - Status: Can be done in parallel with core PR

2. **PyPI Package**
   - Requirement: `lojack-api` package must be on PyPI
   - Status: Already available at version 0.6.0

---

## PR Submission Checklist

Before creating the PR:

- [ ] All code formatted with `ruff format`
- [ ] No linting errors from `pylint` and `ruff`
- [ ] No type errors from `mypy`
- [ ] All tests passing
- [ ] Test coverage >= 95%
- [ ] `hassfest` validation passes
- [ ] `requirements_all.txt` updated
- [ ] Commit messages are clear and descriptive
- [ ] PR description includes:
  - Summary of the integration
  - Link to lojack-api package
  - Link to documentation PR (when created)
  - Test plan/verification steps

---

## Quality Scale Progression (Future)

After Bronze acceptance, consider these enhancements for Silver/Gold:

### Silver Level
- [ ] `config-entry-unloading`: Graceful unload (already implemented)
- [ ] `reauthentication-flow`: Handle expired credentials (already implemented)
- [ ] `parallel-updates`: Use `async_add_executor_job` for blocking ops
- [ ] `docs-configuration-parameters`: Document all config options

### Gold Level
- [ ] `diagnostics`: Add diagnostics.py for debug info
- [ ] `entity-translations`: Full translation support for entities
- [ ] `log-when-unavailable`: Log device unavailability state changes
- [ ] `docs-known-limitations`: Document API rate limits and restrictions

### Platinum Level
- [ ] `strict-typing`: Full mypy strict mode compliance
- [ ] `async-dependency`: Ensure lojack-api uses only async I/O
- [ ] `inject-websession`: Use HA's aiohttp session

---

## Contact and Support

- **Code Owner**: @devinslick
- **Integration Repository**: https://github.com/devinslick/homeassistant_lojack
- **API Package**: https://pypi.org/project/lojack-api/

---

*Last Updated: 2026-01-31*
