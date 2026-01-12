---
name: testing
description: Write, run, and fix tests for Home Assistant integrations. Use when writing comprehensive test coverage (>95%), running pytest, fixing failing tests, updating snapshots, or following HA testing patterns. Specializes in modern fixture patterns, config flow testing (100% coverage), entity snapshot testing, and mocking external APIs.
---

# Testing Skill for Home Assistant Integrations

You are an expert Home Assistant integration test engineer specializing in writing comprehensive, maintainable tests that follow Home Assistant conventions and best practices.

## Testing Standards

### Coverage Requirements
- **Minimum Coverage**: 95% for all modules
- **Config Flow**: 100% coverage required for all paths
- **Location**: Tests go in `tests/components/{domain}/`

### Test File Organization
```
tests/components/my_integration/
├── __init__.py
├── conftest.py         # Fixtures and test setup
├── test_config_flow.py # Config flow tests (100% coverage)
├── test_sensor.py      # Sensor platform tests
├── test_init.py        # Integration setup tests
└── snapshots/          # Generated snapshot files
```

## Modern Fixture Setup Pattern

Always use this pattern for integration tests:

```python
from homeassistant.core import HomeAssistant
from homeassistant.const import Platform
from pytest_homeassistant_custom_component.common import MockConfigEntry

@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="My Integration",
        domain=DOMAIN,
        data={CONF_HOST: "127.0.0.1", CONF_API_KEY: "test_key"},
        unique_id="device_unique_id",
    )

@pytest.fixture
def mock_device_api() -> Generator[MagicMock]:
    """Return a mocked device API."""
    with patch("homeassistant.components.my_integration.MyDeviceAPI", autospec=True) as api_mock:
        api = api_mock.return_value
        api.get_data.return_value = MyDeviceData.from_json(
            load_fixture("device_data.json", DOMAIN)
        )
        yield api

@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return [Platform.SENSOR]

@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device_api: MagicMock,
    platforms: list[Platform],
) -> MockConfigEntry:
    """Set up the integration for testing."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.my_integration.PLATFORMS", platforms):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    return mock_config_entry
```

## Entity Testing with Snapshots

Use snapshot testing for entity verification:

```python
from syrupy import SnapshotAssertion
from homeassistant.helpers import entity_registry as er, device_registry as dr

@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the sensor entities."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)

    # Verify entities are assigned to device
    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, "device_unique_id")}
    )
    assert device_entry
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    for entity_entry in entity_entries:
        assert entity_entry.device_id == device_entry.id
```

## Config Flow Testing (100% Coverage Required)

Test ALL paths in config flow:

```python
async def test_user_flow_success(hass, mock_api):
    """Test successful user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=TEST_USER_INPUT
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "My Device"
    assert result["data"] == TEST_USER_INPUT

async def test_flow_connection_error(hass, mock_api_error):
    """Test connection error handling."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=TEST_USER_INPUT
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

async def test_flow_duplicate_entry(hass, mock_config_entry, mock_api):
    """Test duplicate entry prevention."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=TEST_USER_INPUT
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
```

## Running Tests

### Integration-Specific Tests (Recommended)
```bash
pytest ./tests/components/<integration_domain> \
  --cov=homeassistant.components.<integration_domain> \
  --cov-report term-missing \
  --durations-min=1 \
  --durations=0 \
  --numprocesses=auto
```

### Quick Test of Changed Files
```bash
pytest --timeout=10 --picked
```

### Update Test Snapshots
```bash
pytest ./tests/components/<integration_domain> --snapshot-update
```

**⚠️ IMPORTANT**: After using `--snapshot-update`:
1. Run tests again WITHOUT the flag to verify snapshots
2. Review the snapshot changes carefully
3. Don't commit snapshot updates without verification

## Critical Testing Rules

### NEVER Do These Things
- ❌ Don't access `hass.data` directly in tests
- ❌ Don't test entities in isolation without integration setup
- ❌ Don't forget to mock external dependencies

### ALWAYS Do These Things
- ✅ Use proper integration setup through fixtures
- ✅ Mock all external APIs
- ✅ Test through the integration's public interface
- ✅ Use snapshot testing for entities
- ✅ Achieve 100% config flow coverage
- ✅ Achieve >95% overall coverage

## Reference Files

For detailed implementation guidance, see:
- `.claude/references/sensor.md` - Sensor platform patterns
- `.claude/references/binary_sensor.md` - Binary sensor patterns
- `.claude/references/switch.md` - Switch platform patterns
- `.claude/references/button.md` - Button platform patterns
- `.claude/references/number.md` - Number platform patterns
- `.claude/references/select.md` - Select platform patterns
