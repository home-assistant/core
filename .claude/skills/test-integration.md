# Skill: Test Integration

Use this skill when writing or fixing tests for a Home Assistant integration.

## Workflow

### Step 1: Understand test structure

Tests are located in `tests/components/<domain>/`:
```
tests/components/<domain>/
├── __init__.py
├── conftest.py          # Shared fixtures
├── test_config_flow.py  # Config flow tests (100% coverage required)
├── test_sensor.py       # Platform-specific tests
├── test_init.py         # Setup/unload tests
├── test_diagnostics.py  # Diagnostics tests
└── snapshots/           # Snapshot files
```

### Step 2: Set up fixtures in conftest.py

```python
import pytest
from unittest.mock import MagicMock, patch
from collections.abc import Generator

from homeassistant.const import CONF_HOST, CONF_API_KEY
from homeassistant.core import HomeAssistant

from pytest_homeassistant_custom_component.common import MockConfigEntry

from .const import DOMAIN

@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="Test Device",
        domain=DOMAIN,
        data={CONF_HOST: "192.168.1.100", CONF_API_KEY: "test_key"},
        unique_id="test_unique_id",
    )

@pytest.fixture
def mock_api() -> Generator[MagicMock]:
    """Return a mocked API client."""
    with patch(
        "homeassistant.components.<domain>.Client",
        autospec=True
    ) as mock:
        client = mock.return_value
        client.get_data.return_value = {"temperature": 22.5}
        yield client

@pytest.fixture
def platforms() -> list[Platform]:
    """Platforms to load for tests."""
    return PLATFORMS

@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: MagicMock,
    platforms: list[Platform],
) -> MockConfigEntry:
    """Set up the integration for testing."""
    mock_config_entry.add_to_hass(hass)
    with patch("homeassistant.components.<domain>.PLATFORMS", platforms):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
    return mock_config_entry
```

### Step 3: Write config flow tests

**Must cover 100% of config flow paths:**

```python
async def test_user_flow_success(hass: HomeAssistant, mock_api: MagicMock) -> None:
    """Test successful user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "192.168.1.100", CONF_API_KEY: "key"},
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY

async def test_user_flow_cannot_connect(
    hass: HomeAssistant, mock_api: MagicMock
) -> None:
    """Test connection error."""
    mock_api.get_data.side_effect = ConnectionError()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "192.168.1.100", CONF_API_KEY: "key"},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

async def test_user_flow_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test duplicate config."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "192.168.1.100", CONF_API_KEY: "key"},
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
```

### Step 4: Write entity tests with snapshots

```python
@pytest.fixture
def platforms() -> list[Platform]:
    """Test only sensors."""
    return [Platform.SENSOR]

@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_sensors(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensor entities."""
    await snapshot_platform(
        hass, entity_registry, snapshot, mock_config_entry.entry_id
    )
```

### Step 5: Run tests

```bash
# Run with coverage
pytest ./tests/components/<domain> \
  --cov=homeassistant.components.<domain> \
  --cov-report term-missing \
  --numprocesses=auto

# Update snapshots if needed
pytest ./tests/components/<domain> --snapshot-update

# Verify snapshots (run again without update flag)
pytest ./tests/components/<domain>
```

## Key Reminders

- **Never access `hass.data` directly** - use fixtures
- **Mock all external calls** - no real network/device access
- **Use `load_fixture()`** for realistic JSON data
- **Snapshot testing** for entity states and attributes
- **Test error paths** not just happy paths

## Common Test Patterns

| Scenario | Pattern |
|----------|---------|
| Test entities | `@pytest.mark.usefixtures("init_integration")` |
| Mock API error | `mock_api.method.side_effect = Exception()` |
| Time-based tests | `freezegun.freeze_time()` or `async_fire_time_changed()` |
| State changes | `hass.states.async_set()` then `await hass.async_block_till_done()` |

## Debug Tips

```python
# Enable debug logging
caplog.set_level(logging.DEBUG, logger="homeassistant.components.<domain>")

# Check logs
assert "Expected message" in caplog.text
```
