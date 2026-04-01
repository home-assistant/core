"""Test the ISS integration setup and coordinator."""

from unittest.mock import MagicMock

from requests.exceptions import ConnectionError as RequestsConnectionError, HTTPError

from homeassistant.components.iss.const import MAX_CONSECUTIVE_FAILURES
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE, CONF_SHOW_ON_MAP
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import MockConfigEntry


async def test_setup_entry(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test successful setup of config entry."""
    assert init_integration.state is ConfigEntryState.LOADED
    coordinator = init_integration.runtime_data
    assert coordinator.data is not None
    assert coordinator.data.number_of_people_in_space == 7
    assert coordinator.data.current_location == {
        "latitude": "40.271698",
        "longitude": "15.619478",
    }


async def test_unload_entry(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test unload of config entry."""
    assert init_integration.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()

    assert init_integration.state is ConfigEntryState.NOT_LOADED


async def test_update_listener(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_pyiss: MagicMock
) -> None:
    """Test options update triggers reload and applies new options."""
    state = hass.states.get("sensor.iss")
    assert state is not None
    assert "lat" in state.attributes
    assert "long" in state.attributes
    assert ATTR_LATITUDE not in state.attributes
    assert ATTR_LONGITUDE not in state.attributes

    hass.config_entries.async_update_entry(
        init_integration, options={CONF_SHOW_ON_MAP: True}
    )
    await hass.async_block_till_done()

    # After reload with show_on_map=True, attributes should switch
    state = hass.states.get("sensor.iss")
    assert state is not None
    assert ATTR_LATITUDE in state.attributes
    assert ATTR_LONGITUDE in state.attributes
    assert "lat" not in state.attributes
    assert "long" not in state.attributes


async def test_coordinator_single_failure_uses_cached_data(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_pyiss: MagicMock
) -> None:
    """Test coordinator tolerates single API failure and uses cached data."""
    coordinator = init_integration.runtime_data
    original_data = coordinator.data

    # Simulate API failure
    mock_pyiss.number_of_people_in_space.side_effect = HTTPError("API Error")

    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # Should still have the cached data
    assert coordinator.data == original_data
    assert coordinator.last_update_success is True


async def test_coordinator_multiple_failures_uses_cached_data(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_pyiss: MagicMock
) -> None:
    """Test coordinator tolerates multiple failures below threshold."""
    coordinator = init_integration.runtime_data
    original_data = coordinator.data

    # Simulate multiple API failures (below MAX_CONSECUTIVE_FAILURES)
    mock_pyiss.number_of_people_in_space.side_effect = RequestsConnectionError(
        "Connection failed"
    )

    for _ in range(MAX_CONSECUTIVE_FAILURES - 1):
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    # Should still have cached data and be successful
    assert coordinator.data == original_data
    assert coordinator.last_update_success is True


async def test_coordinator_max_failures_marks_unavailable(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_pyiss: MagicMock
) -> None:
    """Test coordinator marks update failed after MAX_CONSECUTIVE_FAILURES."""
    coordinator = init_integration.runtime_data

    # Simulate consecutive API failures reaching the threshold
    mock_pyiss.number_of_people_in_space.side_effect = HTTPError("API Error")

    for _ in range(MAX_CONSECUTIVE_FAILURES):
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    # After MAX_CONSECUTIVE_FAILURES, update should be marked as failed
    assert coordinator.last_update_success is False
    assert isinstance(coordinator.last_exception, UpdateFailed)


async def test_coordinator_failure_counter_resets_on_success(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_pyiss: MagicMock
) -> None:
    """Test coordinator resets failure counter after successful fetch."""
    coordinator = init_integration.runtime_data

    # Simulate some failures
    mock_pyiss.number_of_people_in_space.side_effect = HTTPError("API Error")
    for _ in range(2):
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    # Now simulate success
    mock_pyiss.number_of_people_in_space.side_effect = None
    mock_pyiss.number_of_people_in_space.return_value = 8
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert coordinator.last_update_success is True
    assert coordinator.data.number_of_people_in_space == 8

    # Failure counter should be reset, so we can tolerate failures again
    mock_pyiss.number_of_people_in_space.side_effect = RequestsConnectionError(
        "Connection failed"
    )
    for _ in range(MAX_CONSECUTIVE_FAILURES - 1):
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    # Should still be successful due to cached data
    assert coordinator.last_update_success is True


async def test_coordinator_initial_failure_no_cached_data(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_pyiss: MagicMock
) -> None:
    """Test coordinator fails immediately on initial setup with no cached data."""
    mock_pyiss.number_of_people_in_space.side_effect = HTTPError("API Error")
    mock_config_entry.add_to_hass(hass)

    # Setup should fail because there's no cached data
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_coordinator_handles_connection_error(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_pyiss: MagicMock
) -> None:
    """Test coordinator handles ConnectionError exceptions."""
    coordinator = init_integration.runtime_data
    original_data = coordinator.data

    # Simulate ConnectionError
    mock_pyiss.current_location.side_effect = RequestsConnectionError(
        "Network unreachable"
    )

    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # Should use cached data
    assert coordinator.data == original_data
    assert coordinator.last_update_success is True
