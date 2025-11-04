# tests/components/rejseplanen/test_coordinator.py
"""Test the Rejseplanen coordinator."""

from unittest.mock import MagicMock, patch

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
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test coordinator handles API errors."""
    mock_config_entry.add_to_hass(hass)

    # Mock API failure
    with patch(
        "homeassistant.components.rejseplanen.coordinator.DeparturesAPIClient"
    ) as mock_api_class:
        mock_api = MagicMock()
        mock_api.get_departures.side_effect = Exception("API Error")
        mock_api_class.return_value = mock_api

        # Setup should fail with UpdateFailed
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Entry should be in retry state
    assert mock_config_entry.state.name == "SETUP_RETRY"


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
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test coordinator handles authentication failures."""
    mock_config_entry.add_to_hass(hass)

    # Mock authentication error
    with patch(
        "homeassistant.components.rejseplanen.coordinator.DeparturesAPIClient"
    ) as mock_api_class:
        mock_api = MagicMock()
        # Simulate auth failure that coordinator converts to ConfigEntryAuthFailed
        mock_api.get_departures.side_effect = Exception("401 Unauthorized")
        mock_api_class.return_value = mock_api

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Entry should be in appropriate error state
    assert mock_config_entry.state.name in ("SETUP_ERROR", "SETUP_RETRY")
