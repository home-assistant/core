# Testing Patterns

## Test Location

Tests go in `tests/components/{domain}/`.

## Coverage Requirement

Above 95% test coverage for all modules.

## Modern Fixture Setup

```python
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
    with patch(
        "homeassistant.components.my_integration.MyDeviceAPI",
        autospec=True
    ) as api_mock:
        api = api_mock.return_value
        api.get_data.return_value = MyDeviceData.from_json(
            load_fixture("device_data.json", DOMAIN)
        )
        yield api

@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return PLATFORMS

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

## Config Flow Testing

100% coverage required for all config flow paths:

```python
async def test_user_flow_success(hass: HomeAssistant, mock_api: MagicMock) -> None:
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

async def test_flow_connection_error(
    hass: HomeAssistant, mock_api_error: MagicMock
) -> None:
    """Test connection error handling."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=TEST_USER_INPUT
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
```

## Entity Testing with Snapshots

```python
@pytest.fixture
def platforms() -> list[Platform]:
    """Overridden fixture to specify platforms to test."""
    return [Platform.SENSOR]

@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the sensor entities."""
    await snapshot_platform(
        hass, entity_registry, snapshot, mock_config_entry.entry_id
    )

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

## Snapshot Updates

```bash
# Update snapshots
pytest ./tests/components/<domain> --snapshot-update

# Always run again without flag to verify
pytest ./tests/components/<domain>
```

## Testing Commands

```bash
# Integration-specific tests with coverage
pytest ./tests/components/<domain> \
  --cov=homeassistant.components.<domain> \
  --cov-report term-missing \
  --durations-min=1 \
  --durations=0 \
  --numprocesses=auto

# Quick test of changed files
pytest --timeout=10 --picked
```

## Mock Patterns

**Never access `hass.data` directly** - use fixtures and proper setup instead.

**Use fixtures with realistic JSON data**:
```python
api.get_data.return_value = MyDeviceData.from_json(
    load_fixture("device_data.json", DOMAIN)
)
```

## Debug Logging in Tests

```python
async def test_something(hass: HomeAssistant, caplog: pytest.LogCaptureFixture) -> None:
    """Test with logging."""
    caplog.set_level(logging.DEBUG, logger="homeassistant.components.my_integration")
    # ... test code
    assert "Expected log message" in caplog.text
```

## Testing Best Practices

- Test through integration setup, not entities in isolation
- Mock all external dependencies
- Use snapshots for complex data structures
- Follow existing test patterns in the codebase
- Verify registries (entity and device)
