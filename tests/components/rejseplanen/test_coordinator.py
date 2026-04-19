"""Tests for the Rejseplanen coordinator and setup entry."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from py_rejseplan.enums import TransportClass
from py_rejseplan.exceptions.api_error import APIError
from py_rejseplan.exceptions.connection_error import ConnectionError
from py_rejseplan.exceptions.http_error import HTTPError
import pytest

from homeassistant.components.rejseplanen.helpers import COPENHAGEN_TZ
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import UpdateFailed

from .conftest import make_mock_departures

from tests.common import MockConfigEntry


async def test_setup_entry_first_refresh_fails(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AsyncMock,
) -> None:
    """Test that a failing first refresh raises ConfigEntryNotReady."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.rejseplanen.RejseplanenDataUpdateCoordinator"
        ".async_config_entry_first_refresh",
        side_effect=ConfigEntryNotReady("API unavailable"),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    "error",
    [
        APIError("api error"),
        HTTPError("http error"),
        ConnectionError(
            "Connection error while fetching data: ConnectionError: connection error"
        ),
        TypeError("type error"),
    ],
)
async def test_coordinator_fetch_errors(
    setup_integration, mock_config_entry, error
) -> None:
    """Test that different exceptions during data fetch are handled as UpdateFailed."""
    coordinator = mock_config_entry.runtime_data

    with (
        patch.object(coordinator, "_fetch_data", side_effect=error),
        pytest.raises(UpdateFailed),
    ):
        await coordinator._async_update_data()


async def test_coordinator_fetch_data_with_stops(
    hass: HomeAssistant,
    setup_integration: None,
    mock_config_entry: MockConfigEntry,
    mock_api: AsyncMock,
) -> None:
    """Test _fetch_data with actual stop IDs covers lines 82-84."""
    coordinator = mock_config_entry.runtime_data

    # Trigger a refresh after entities are registered so async_contexts() is non-empty
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # Verify the API was called with stop IDs (lines 82-84 executed)
    assert mock_api.get_departures.called


async def test_coordinator_get_filtered_departures_no_data(
    hass: HomeAssistant,
    setup_integration: None,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test get_filtered_departures returns empty list when coordinator has no data."""
    coordinator = mock_config_entry.runtime_data
    coordinator.data = None

    result = coordinator.get_filtered_departures(stop_id=123456)

    assert result == []


async def test_coordinator_get_filtered_departures_with_data(
    hass: HomeAssistant,
    setup_integration: None,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test get_filtered_departures returns departures when coordinator has data."""
    coordinator = mock_config_entry.runtime_data

    mock_board = MagicMock()
    mock_board.departures = make_mock_departures(456789)
    coordinator.data = mock_board
    fixed_utc = datetime(2024, 1, 1, 11, 0, 0, tzinfo=COPENHAGEN_TZ)

    with patch(
        "homeassistant.components.rejseplanen.coordinator.dt_util.utcnow",
        return_value=fixed_utc,
    ):
        result = coordinator.get_filtered_departures(stop_id=456789)
        assert len(result) == 3

        result = coordinator.get_filtered_departures(stop_id=123456)
        assert len(result) == 0

        result = coordinator.get_filtered_departures(
            stop_id=456789, departure_type_filter=int(TransportClass.ICL)
        )
        assert len(result) == 1

        result = coordinator.get_filtered_departures(
            stop_id=456789, direction_filter=["South"]
        )
        assert len(result) == 1
