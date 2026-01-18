# Mocking Patterns Reference

## Basic Mock Setup

```python
from unittest.mock import AsyncMock, MagicMock, patch

@pytest.fixture
def mock_client() -> Generator[MagicMock]:
    """Mock the client library."""
    with patch(
        "homeassistant.components.my_integration.MyClient",
        autospec=True,
    ) as mock:
        client = mock.return_value
        client.async_get_data = AsyncMock(return_value=MOCK_DATA)
        yield client
```

## Patching Locations

```python
# Patch where the object is used, not where it's defined
with patch("homeassistant.components.my_integration.MyClient"):
    pass

# Not where it's imported from
# with patch("my_library.MyClient"):  # Wrong!
```

## Context Manager Mocks

```python
@pytest.fixture
def mock_client() -> Generator[MagicMock]:
    """Mock client as context manager."""
    with patch(
        "homeassistant.components.my_integration.MyClient",
    ) as mock:
        client = MagicMock()
        mock.return_value.__aenter__.return_value = client
        client.async_get_data = AsyncMock(return_value=MOCK_DATA)
        yield client
```

## Side Effects

```python
# Raise exception
mock_client.async_get_data.side_effect = ConnectionError("Network error")

# Return different values on each call
mock_client.async_get_data.side_effect = [data1, data2, data3]

# Custom function
def custom_side_effect(*args):
    if args[0] == "special":
        return special_data
    return normal_data

mock_client.async_get_data.side_effect = custom_side_effect
```

## Verifying Calls

```python
# Assert called
mock_client.async_get_data.assert_called_once()

# Assert with arguments
mock_client.async_set_value.assert_called_once_with("key", 42)

# Assert any call
mock_client.async_set_value.assert_any_call("key", 42)

# Assert call count
assert mock_client.async_get_data.call_count == 3

# Assert not called
mock_client.async_dangerous_action.assert_not_called()
```

## PropertyMock

```python
from unittest.mock import PropertyMock

@pytest.fixture
def mock_client() -> Generator[MagicMock]:
    """Mock client with property."""
    with patch(
        "homeassistant.components.my_integration.MyClient",
        autospec=True,
    ) as mock:
        client = mock.return_value
        type(client).is_connected = PropertyMock(return_value=True)
        yield client
```

## Mocking Multiple Objects

```python
@pytest.fixture
def mock_dependencies() -> Generator[tuple[MagicMock, MagicMock]]:
    """Mock multiple dependencies."""
    with (
        patch("homeassistant.components.my_integration.FirstClient") as mock_first,
        patch("homeassistant.components.my_integration.SecondClient") as mock_second,
    ):
        yield mock_first.return_value, mock_second.return_value
```

## Coordinator Refresh

```python
async def test_coordinator_refresh(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test coordinator data refresh."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Trigger refresh
    mock_client.async_get_data.return_value = NEW_DATA
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=5))
    await hass.async_block_till_done()

    # Verify new state
    state = hass.states.get("sensor.my_sensor")
    assert state.state == "new_value"
```

## Time-Based Testing

```python
from homeassistant.util import dt as dt_util
from tests.common import async_fire_time_changed

async def test_polling(hass: HomeAssistant) -> None:
    """Test polling updates."""
    # Setup integration

    # Fast forward time
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=5))
    await hass.async_block_till_done()

    # Verify update was called
    mock_client.async_get_data.assert_called()
```
