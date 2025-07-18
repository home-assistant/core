"""Test the Nederlandse Spoorwegen API wrapper."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import zoneinfo

import pytest

from homeassistant.components.nederlandse_spoorwegen.api import (
    NSAPIAuthError,
    NSAPIConnectionError,
    NSAPIError,
    NSAPIWrapper,
    get_ns_api_version,
)
from homeassistant.core import HomeAssistant


@pytest.fixture
def mock_hass():
    """Return a mock Home Assistant instance."""
    hass = MagicMock(spec=HomeAssistant)
    hass.async_add_executor_job = AsyncMock()
    return hass


@pytest.fixture
def api_wrapper(mock_hass):
    """Return an NSAPIWrapper instance."""
    return NSAPIWrapper(mock_hass, "test_api_key")


def test_get_ns_api_version() -> None:
    """Test that we can get the ns_api version."""
    with patch(
        "homeassistant.components.nederlandse_spoorwegen.api.ns_api"
    ) as mock_ns_api:
        mock_ns_api.__version__ = "3.1.2"
        version = get_ns_api_version()
        assert version == "3.1.2"


class TestNSAPIWrapper:
    """Test the NSAPIWrapper class."""

    @pytest.mark.asyncio
    async def test_validate_api_key_success(self, api_wrapper, mock_hass):
        """Test successful API key validation."""
        # Mock successful station fetch
        mock_stations = [{"code": "AMS", "name": "Amsterdam Centraal"}]
        mock_hass.async_add_executor_job.return_value = mock_stations

        result = await api_wrapper.validate_api_key()
        assert result is True
        mock_hass.async_add_executor_job.assert_called_once()

    @pytest.mark.asyncio
    async def test_validate_api_key_auth_error(self, api_wrapper, mock_hass):
        """Test API key validation with auth error."""
        # Mock auth error
        mock_hass.async_add_executor_job.side_effect = ValueError("401 Unauthorized")

        with pytest.raises(NSAPIAuthError, match="Invalid API key"):
            await api_wrapper.validate_api_key()

    @pytest.mark.asyncio
    async def test_validate_api_key_connection_error(self, api_wrapper, mock_hass):
        """Test API key validation with connection error."""
        # Mock connection error
        mock_hass.async_add_executor_job.side_effect = ConnectionError(
            "Connection failed"
        )

        with pytest.raises(NSAPIConnectionError, match="Failed to connect to NS API"):
            await api_wrapper.validate_api_key()

    @pytest.mark.asyncio
    async def test_get_stations_success(self, api_wrapper, mock_hass):
        """Test successful station fetch."""
        mock_stations = [
            {"code": "AMS", "name": "Amsterdam Centraal"},
            {"code": "UTR", "name": "Utrecht Centraal"},
        ]
        mock_hass.async_add_executor_job.return_value = mock_stations

        stations = await api_wrapper.get_stations()
        assert stations == mock_stations
        mock_hass.async_add_executor_job.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_trips_with_filtering(self, api_wrapper, mock_hass):
        """Test get_trips with past trip filtering."""
        # Setup timezone
        nl_tz = zoneinfo.ZoneInfo("Europe/Amsterdam")
        now = datetime.now(nl_tz)

        # Create mock trips - some in past, some in future
        past_trip = MagicMock()
        past_trip.departure_time_actual = None
        past_trip.departure_time_planned = now - timedelta(hours=1)  # 1 hour ago

        future_trip1 = MagicMock()
        future_trip1.departure_time_actual = now + timedelta(
            minutes=30
        )  # 30 min from now
        future_trip1.departure_time_planned = now + timedelta(minutes=30)

        future_trip2 = MagicMock()
        future_trip2.departure_time_actual = None
        future_trip2.departure_time_planned = now + timedelta(
            hours=1
        )  # 1 hour from now

        current_trip = MagicMock()
        current_trip.departure_time_actual = now  # Exactly now (should be filtered)
        current_trip.departure_time_planned = now

        all_trips = [past_trip, future_trip1, future_trip2, current_trip]
        mock_hass.async_add_executor_job.return_value = all_trips

        # Test the filtering
        with patch(
            "homeassistant.components.nederlandse_spoorwegen.api.dt_util.now"
        ) as mock_now:
            mock_now.return_value = now
            trips = await api_wrapper.get_trips("AMS", "UTR")

        # Should only return future trips (trip with departure_time > now)
        assert len(trips) == 2
        assert future_trip1 in trips
        assert future_trip2 in trips
        assert past_trip not in trips
        assert current_trip not in trips  # exactly now should be filtered out

    @pytest.mark.asyncio
    async def test_get_trips_empty_list(self, api_wrapper, mock_hass):
        """Test get_trips with empty result."""
        mock_hass.async_add_executor_job.return_value = []

        trips = await api_wrapper.get_trips("AMS", "UTR")
        assert trips == []

    @pytest.mark.asyncio
    async def test_get_trips_none_result(self, api_wrapper, mock_hass):
        """Test get_trips with None result."""
        mock_hass.async_add_executor_job.return_value = None

        trips = await api_wrapper.get_trips("AMS", "UTR")
        assert trips == []

    @pytest.mark.asyncio
    async def test_get_trips_with_departure_time(self, api_wrapper, mock_hass):
        """Test get_trips with specific departure time."""
        nl_tz = zoneinfo.ZoneInfo("Europe/Amsterdam")
        departure_time = datetime(2024, 1, 15, 10, 30, 0, tzinfo=nl_tz)

        future_trip = MagicMock()
        future_trip.departure_time_actual = None
        future_trip.departure_time_planned = departure_time + timedelta(minutes=30)

        mock_hass.async_add_executor_job.return_value = [future_trip]

        with patch(
            "homeassistant.components.nederlandse_spoorwegen.api.dt_util.now"
        ) as mock_now:
            mock_now.return_value = departure_time - timedelta(hours=1)  # 1 hour before
            trips = await api_wrapper.get_trips(
                "AMS", "UTR", departure_time=departure_time
            )

        assert len(trips) == 1
        assert trips[0] == future_trip

        # Verify the executor job was called with formatted timestamp
        mock_hass.async_add_executor_job.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_trips_auth_error(self, api_wrapper, mock_hass):
        """Test get_trips with authentication error."""
        mock_hass.async_add_executor_job.side_effect = ValueError("401 Unauthorized")

        with pytest.raises(NSAPIAuthError, match="Invalid API key"):
            await api_wrapper.get_trips("AMS", "UTR")

    @pytest.mark.asyncio
    async def test_get_trips_connection_error(self, api_wrapper, mock_hass):
        """Test get_trips with connection error."""
        mock_hass.async_add_executor_job.side_effect = ConnectionError("Network error")

        with pytest.raises(NSAPIConnectionError, match="Failed to connect to NS API"):
            await api_wrapper.get_trips("AMS", "UTR")

    @pytest.mark.asyncio
    async def test_get_trips_unexpected_error(self, api_wrapper, mock_hass):
        """Test get_trips with unexpected error."""
        mock_hass.async_add_executor_job.side_effect = RuntimeError("Unexpected error")

        with pytest.raises(NSAPIError, match="Unexpected error getting trips"):
            await api_wrapper.get_trips("AMS", "UTR")

    def test_filter_future_trips_empty_list(self, api_wrapper):
        """Test _filter_future_trips with empty list."""
        result = api_wrapper._filter_future_trips([])
        assert result == []

    def test_filter_future_trips_mixed_times(self, api_wrapper):
        """Test _filter_future_trips with mixed past/future times."""
        nl_tz = zoneinfo.ZoneInfo("Europe/Amsterdam")

        # Mock current time
        mock_now = datetime(2024, 1, 15, 12, 0, 0, tzinfo=nl_tz)

        # Create test trips
        past_trip = MagicMock()
        past_trip.departure_time_actual = mock_now - timedelta(hours=1)
        past_trip.departure_time_planned = mock_now - timedelta(hours=1)

        future_trip = MagicMock()
        future_trip.departure_time_actual = None
        future_trip.departure_time_planned = mock_now + timedelta(hours=1)

        no_time_trip = MagicMock()
        no_time_trip.departure_time_actual = None
        no_time_trip.departure_time_planned = None

        trips = [past_trip, future_trip, no_time_trip]

        with patch(
            "homeassistant.components.nederlandse_spoorwegen.api.dt_util.now"
        ) as mock_dt_now:
            mock_dt_now.return_value = mock_now
            result = api_wrapper._filter_future_trips(trips)

        # Only future_trip should remain
        assert len(result) == 1
        assert result[0] == future_trip

    def test_filter_future_trips_prefers_actual_time(self, api_wrapper):
        """Test _filter_future_trips prefers actual over planned time."""
        nl_tz = zoneinfo.ZoneInfo("Europe/Amsterdam")
        mock_now = datetime(2024, 1, 15, 12, 0, 0, tzinfo=nl_tz)

        # Trip with actual time in future, planned time in past
        trip = MagicMock()
        trip.departure_time_actual = mock_now + timedelta(minutes=30)  # Future
        trip.departure_time_planned = mock_now - timedelta(minutes=30)  # Past

        with patch(
            "homeassistant.components.nederlandse_spoorwegen.api.dt_util.now"
        ) as mock_dt_now:
            mock_dt_now.return_value = mock_now
            result = api_wrapper._filter_future_trips([trip])

        # Should use actual time (future) and include the trip
        assert len(result) == 1
        assert result[0] == trip
