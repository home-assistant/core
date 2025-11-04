# tests/components/rejseplanen/test_coordinator.py
"""Test the Rejseplanen coordinator."""

from unittest.mock import MagicMock, patch

from requests.exceptions import HTTPError

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_coordinator_successful_update(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test coordinator successful data update."""
    mock_config_entry.add_to_hass(hass)

    # Mock successful API response
    with patch(
        "homeassistant.components.rejseplanen.coordinator.DeparturesAPIClient"
    ) as mock_api_class:
        mock_api = MagicMock()
        mock_api.get_departures.return_value = (
            MagicMock(departures=[{"line": "A", "direction": "North"}]),
            [],
        )
        mock_api_class.return_value = mock_api

        # Setup integration - this triggers first refresh
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Verify coordinator was created and has data
    assert mock_config_entry.runtime_data is not None
    coordinator = mock_config_entry.runtime_data
    assert coordinator.last_update_success is True


async def test_coordinator_update_failed(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test coordinator handles API errors during refresh."""
    coordinator = init_integration.runtime_data

    # Mock API failure for the coordinator's update
    with patch.object(coordinator, "_fetch_data", side_effect=Exception("API Error")):
        # Trigger a refresh that should fail
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    # Coordinator should indicate update failure
    assert not coordinator.last_update_success


async def test_coordinator_add_remove_stop_id(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test coordinator stop ID management."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.rejseplanen.coordinator.DeparturesAPIClient"
    ) as mock_api_class:
        mock_api = MagicMock()
        mock_api.get_departures.return_value = (MagicMock(departures=[]), [])
        mock_api_class.return_value = mock_api

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data

    # Test adding stop IDs
    coordinator.add_stop_id(12345)
    coordinator.add_stop_id(67890)

    assert 12345 in coordinator._stop_ids
    assert 67890 in coordinator._stop_ids

    # Test removing stop ID
    coordinator.remove_stop_id(12345)
    assert 12345 not in coordinator._stop_ids
    assert 67890 in coordinator._stop_ids


async def test_coordinator_auth_failed(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test coordinator handles authentication failures during refresh."""
    coordinator = init_integration.runtime_data

    # Mock auth failure during coordinator update
    with patch.object(
        coordinator, "_fetch_data", side_effect=HTTPError("401 Unauthorized")
    ):
        # Trigger a refresh that should fail with auth error
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    # Coordinator should indicate update failure
    assert not coordinator.last_update_success
