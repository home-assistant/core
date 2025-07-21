"""Test the Nederlandse Spoorwegen API wrapper."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, Mock, patch
import zoneinfo

import pytest
from requests.exceptions import (
    ConnectionError as RequestsConnectionError,
    HTTPError,
    Timeout,
)

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
        # Create a proper HTTPError with 401 status
        response_mock = Mock()
        response_mock.status_code = 401
        http_error = HTTPError("401 Unauthorized")
        http_error.response = response_mock

        mock_hass.async_add_executor_job.side_effect = http_error

        with pytest.raises(NSAPIAuthError, match="Invalid API key"):
            await api_wrapper.validate_api_key()

    @pytest.mark.asyncio
    async def test_validate_api_key_connection_error(self, api_wrapper, mock_hass):
        """Test API key validation with connection error."""
        # Mock connection error
        mock_hass.async_add_executor_job.side_effect = RequestsConnectionError(
            "Connection failed"
        )

        with pytest.raises(NSAPIConnectionError, match="Failed to connect to NS API"):
            await api_wrapper.validate_api_key()

    @pytest.mark.asyncio
    async def test_validate_api_key_value_error(self, api_wrapper, mock_hass):
        """Test API key validation with ValueError (treated as connection error)."""
        # Mock ValueError (no more string parsing)
        mock_hass.async_add_executor_job.side_effect = ValueError("API error")

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

    @pytest.mark.asyncio
    async def test_get_departures_success(self, api_wrapper, mock_hass):
        """Test successful departures fetch."""
        mock_departures = [
            {"departure": "10:30", "destination": "Utrecht"},
            {"departure": "10:45", "destination": "Amsterdam"},
        ]
        mock_hass.async_add_executor_job.return_value = mock_departures

        departures = await api_wrapper.get_departures("AMS")
        assert departures == mock_departures
        mock_hass.async_add_executor_job.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_departures_with_params(self, api_wrapper, mock_hass):
        """Test get_departures with optional parameters."""
        nl_tz = zoneinfo.ZoneInfo("Europe/Amsterdam")
        departure_time = datetime(2024, 1, 15, 10, 30, 0, tzinfo=nl_tz)

        mock_departures = [{"departure": "10:30", "destination": "Utrecht"}]
        mock_hass.async_add_executor_job.return_value = mock_departures

        departures = await api_wrapper.get_departures(
            "AMS", departure_time=departure_time, max_journeys=10
        )
        assert departures == mock_departures

    @pytest.mark.asyncio
    async def test_get_departures_none_result(self, api_wrapper, mock_hass):
        """Test get_departures with None result."""
        mock_hass.async_add_executor_job.return_value = None

        departures = await api_wrapper.get_departures("AMS")
        assert departures == []

    @pytest.mark.asyncio
    async def test_get_departures_auth_error(self, api_wrapper, mock_hass):
        """Test get_departures with authentication error."""
        mock_hass.async_add_executor_job.side_effect = ValueError("401 Unauthorized")

        with pytest.raises(NSAPIAuthError, match="Invalid API key"):
            await api_wrapper.get_departures("AMS")

    @pytest.mark.asyncio
    async def test_get_departures_connection_error(self, api_wrapper, mock_hass):
        """Test get_departures with connection error."""
        mock_hass.async_add_executor_job.side_effect = ConnectionError("Network error")

        with pytest.raises(NSAPIConnectionError, match="Failed to connect to NS API"):
            await api_wrapper.get_departures("AMS")

    @pytest.mark.asyncio
    async def test_get_departures_unexpected_error(self, api_wrapper, mock_hass):
        """Test get_departures with unexpected error."""
        mock_hass.async_add_executor_job.side_effect = RuntimeError("Unexpected error")

        with pytest.raises(NSAPIError, match="Unexpected error getting departures"):
            await api_wrapper.get_departures("AMS")

    @pytest.mark.asyncio
    async def test_get_disruptions_success(self, api_wrapper, mock_hass):
        """Test successful disruptions fetch."""
        mock_disruptions = {"disruptions": [{"title": "Track work"}]}
        mock_hass.async_add_executor_job.return_value = mock_disruptions

        disruptions = await api_wrapper.get_disruptions()
        assert disruptions == mock_disruptions
        mock_hass.async_add_executor_job.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_disruptions_with_station(self, api_wrapper, mock_hass):
        """Test get_disruptions with station parameter."""
        mock_disruptions = {"disruptions": [{"title": "Platform issue"}]}
        mock_hass.async_add_executor_job.return_value = mock_disruptions

        disruptions = await api_wrapper.get_disruptions("AMS")
        assert disruptions == mock_disruptions

    @pytest.mark.asyncio
    async def test_get_disruptions_auth_error(self, api_wrapper, mock_hass):
        """Test get_disruptions with authentication error."""
        mock_hass.async_add_executor_job.side_effect = ValueError("401 invalid")

        with pytest.raises(NSAPIAuthError, match="Invalid API key"):
            await api_wrapper.get_disruptions()

    @pytest.mark.asyncio
    async def test_get_disruptions_connection_error(self, api_wrapper, mock_hass):
        """Test get_disruptions with connection error."""
        mock_hass.async_add_executor_job.side_effect = ConnectionError("Network error")

        with pytest.raises(NSAPIConnectionError, match="Failed to connect to NS API"):
            await api_wrapper.get_disruptions()

    @pytest.mark.asyncio
    async def test_get_disruptions_unexpected_error(self, api_wrapper, mock_hass):
        """Test get_disruptions with unexpected error."""
        mock_hass.async_add_executor_job.side_effect = RuntimeError("Unexpected error")

        with pytest.raises(NSAPIError, match="Unexpected error getting disruptions"):
            await api_wrapper.get_disruptions()

    def test_build_station_mapping_standard_format(self, api_wrapper):
        """Test build_station_mapping with standard objects."""
        station1 = MagicMock()
        station1.code = "AMS"
        station1.name = "Amsterdam Centraal"

        station2 = MagicMock()
        station2.code = "UTR"
        station2.name = "Utrecht Centraal"

        stations = [station1, station2]
        mapping = api_wrapper.build_station_mapping(stations)

        assert mapping == {"AMS": "Amsterdam Centraal", "UTR": "Utrecht Centraal"}

    def test_build_station_mapping_dict_format(self, api_wrapper):
        """Test build_station_mapping with dict format."""
        stations = [
            {"code": "AMS", "name": "Amsterdam Centraal"},
            {"code": "UTR", "name": "Utrecht Centraal"},
        ]
        mapping = api_wrapper.build_station_mapping(stations)

        assert mapping == {"AMS": "Amsterdam Centraal", "UTR": "Utrecht Centraal"}

    def test_build_station_mapping_string_format(self, api_wrapper):
        """Test build_station_mapping with string format."""
        stations = [
            "AMS Amsterdam Centraal",
            "UTR Utrecht Centraal",
            "GVC Den Haag Centraal",
        ]
        mapping = api_wrapper.build_station_mapping(stations)

        assert mapping == {
            "AMS": "Amsterdam Centraal",
            "UTR": "Utrecht Centraal",
            "GVC": "Den Haag Centraal",
        }

    def test_build_station_mapping_with_class_wrapper(self, api_wrapper):
        """Test build_station_mapping with class wrapper format."""
        stations = [
            "<Station> AMS Amsterdam Centraal",
            "<Station> UTR Utrecht Centraal",
        ]
        mapping = api_wrapper.build_station_mapping(stations)

        assert mapping == {"AMS": "Amsterdam Centraal", "UTR": "Utrecht Centraal"}

    def test_build_station_mapping_invalid_formats(self, api_wrapper):
        """Test build_station_mapping with invalid formats."""
        stations = [
            "",  # Empty string
            "InvalidFormat",  # No space
            "A" * 201,  # Too long
            "<Station>",  # Malformed wrapper
            "123",  # Only number
            "  ",  # Only spaces
            None,  # None value (will be converted to "None")
        ]
        mapping = api_wrapper.build_station_mapping(stations)

        # Should skip all invalid formats
        assert mapping == {}

    def test_build_station_mapping_edge_cases(self, api_wrapper):
        """Test build_station_mapping with edge case formats."""
        # Test case-insensitive code normalization and trimming
        stations = [
            "  ams  Amsterdam Centraal  ",  # Extra spaces
            "utr Utrecht Centraal",  # Lowercase code
        ]
        mapping = api_wrapper.build_station_mapping(stations)

        assert mapping == {"AMS": "Amsterdam Centraal", "UTR": "Utrecht Centraal"}

    def test_build_station_mapping_with_exceptions(self, api_wrapper):
        """Test build_station_mapping handles exceptions gracefully."""
        # Create a station object that raises exceptions
        bad_station = MagicMock()
        bad_station.code = property(lambda self: 1 / 0)  # Raises ZeroDivisionError

        good_station = MagicMock()
        good_station.code = "AMS"
        good_station.name = "Amsterdam Centraal"

        stations = [bad_station, good_station]
        mapping = api_wrapper.build_station_mapping(stations)

        # Should skip the bad station and process the good one
        assert mapping == {"AMS": "Amsterdam Centraal"}

    def test_build_station_mapping_missing_code_or_name(self, api_wrapper):
        """Test build_station_mapping with missing code or name."""
        stations = [
            {"code": "AMS", "name": ""},  # Empty name
            {"code": "", "name": "Amsterdam Centraal"},  # Empty code
            {"code": "UTR"},  # Missing name
            {"name": "Utrecht Centraal"},  # Missing code
            {"code": None, "name": "Test"},  # None code
            {"code": "TEST", "name": None},  # None name
        ]
        mapping = api_wrapper.build_station_mapping(stations)

        # Should skip all stations with missing or empty code/name
        assert mapping == {}

    def test_get_station_codes_success(self, api_wrapper):
        """Test get_station_codes returns set of station codes."""
        stations = [
            {"code": "AMS", "name": "Amsterdam Centraal"},
            {"code": "UTR", "name": "Utrecht Centraal"},
        ]

        codes = api_wrapper.get_station_codes(stations)
        assert codes == {"AMS", "UTR"}

    def test_get_station_codes_empty(self, api_wrapper):
        """Test get_station_codes with empty stations list."""
        codes = api_wrapper.get_station_codes([])
        assert codes == set()

    def test_normalize_station_code_valid(self, api_wrapper):
        """Test normalize_station_code with valid inputs."""
        assert api_wrapper.normalize_station_code("ams") == "AMS"
        assert api_wrapper.normalize_station_code("  UTR  ") == "UTR"
        assert api_wrapper.normalize_station_code("GVC") == "GVC"

    def test_normalize_station_code_invalid(self, api_wrapper):
        """Test normalize_station_code with invalid inputs."""
        assert api_wrapper.normalize_station_code(None) == ""
        assert api_wrapper.normalize_station_code("") == ""
        assert api_wrapper.normalize_station_code("   ") == ""

    @pytest.mark.asyncio
    async def test_get_stations_http_error_non_401(self, api_wrapper, mock_hass):
        """Test get_stations with non-401 HTTP error."""
        response_mock = Mock()
        response_mock.status_code = 500
        http_error = HTTPError("500 Server Error")
        http_error.response = response_mock

        mock_hass.async_add_executor_job.side_effect = http_error

        with pytest.raises(NSAPIConnectionError, match="Failed to connect to NS API"):
            await api_wrapper.get_stations()

    @pytest.mark.asyncio
    async def test_get_stations_auth_error(self, api_wrapper, mock_hass):
        """Test get_stations with 401 HTTP error."""
        response_mock = Mock()
        response_mock.status_code = 401
        http_error = HTTPError("401 Unauthorized")
        http_error.response = response_mock

        mock_hass.async_add_executor_job.side_effect = http_error

        with pytest.raises(NSAPIAuthError, match="Invalid API key"):
            await api_wrapper.get_stations()

    @pytest.mark.asyncio
    async def test_get_trips_with_via_station(self, api_wrapper, mock_hass):
        """Test get_trips with via station parameter."""
        future_trip = MagicMock()
        nl_tz = zoneinfo.ZoneInfo("Europe/Amsterdam")
        now = datetime.now(nl_tz)
        future_trip.departure_time_actual = None
        future_trip.departure_time_planned = now + timedelta(hours=1)

        mock_hass.async_add_executor_job.return_value = [future_trip]

        with patch(
            "homeassistant.components.nederlandse_spoorwegen.api.dt_util.now"
        ) as mock_now:
            mock_now.return_value = now
            trips = await api_wrapper.get_trips("AMS", "UTR", via_station="GVC")

        assert len(trips) == 1
        assert trips[0] == future_trip

    @pytest.mark.asyncio
    async def test_validate_api_key_http_error_no_response(
        self, api_wrapper, mock_hass
    ):
        """Test API key validation with HTTP error that has no response."""
        http_error = HTTPError("Network error")
        http_error.response = None
        mock_hass.async_add_executor_job.side_effect = http_error

        with pytest.raises(NSAPIConnectionError, match="Failed to connect to NS API"):
            await api_wrapper.validate_api_key()

    @pytest.mark.asyncio
    async def test_validate_api_key_timeout_error(self, api_wrapper, mock_hass):
        """Test API key validation with timeout error."""
        mock_hass.async_add_executor_job.side_effect = Timeout("Request timeout")

        with pytest.raises(NSAPIConnectionError, match="Failed to connect to NS API"):
            await api_wrapper.validate_api_key()

    @pytest.mark.asyncio
    async def test_get_stations_value_error(self, api_wrapper, mock_hass):
        """Test get_stations with ValueError."""
        mock_hass.async_add_executor_job.side_effect = ValueError("Invalid response")

        with pytest.raises(NSAPIConnectionError, match="Failed to connect to NS API"):
            await api_wrapper.get_stations()

    @pytest.mark.asyncio
    async def test_get_stations_connection_error(self, api_wrapper, mock_hass):
        """Test get_stations with connection error."""
        mock_hass.async_add_executor_job.side_effect = RequestsConnectionError(
            "Network error"
        )

        with pytest.raises(NSAPIConnectionError, match="Failed to connect to NS API"):
            await api_wrapper.get_stations()

    @pytest.mark.asyncio
    async def test_get_trips_invalid_auth_message(self, api_wrapper, mock_hass):
        """Test get_trips with auth error based on different invalid message."""
        mock_hass.async_add_executor_job.side_effect = ValueError("unauthorized access")

        with pytest.raises(NSAPIAuthError, match="Invalid API key"):
            await api_wrapper.get_trips("AMS", "UTR")

    @pytest.mark.asyncio
    async def test_get_trips_timeout_error(self, api_wrapper, mock_hass):
        """Test get_trips with timeout error."""
        mock_hass.async_add_executor_job.side_effect = TimeoutError(
            "Operation timed out"
        )

        with pytest.raises(NSAPIConnectionError, match="Failed to connect to NS API"):
            await api_wrapper.get_trips("AMS", "UTR")

    @pytest.mark.asyncio
    async def test_get_departures_invalid_auth_keyword(self, api_wrapper, mock_hass):
        """Test get_departures with auth error based on 'invalid' keyword."""
        mock_hass.async_add_executor_job.side_effect = ValueError("invalid api token")

        with pytest.raises(NSAPIAuthError, match="Invalid API key"):
            await api_wrapper.get_departures("AMS")

    @pytest.mark.asyncio
    async def test_get_departures_timeout_error(self, api_wrapper, mock_hass):
        """Test get_departures with timeout error."""
        mock_hass.async_add_executor_job.side_effect = TimeoutError("Request timeout")

        with pytest.raises(NSAPIConnectionError, match="Failed to connect to NS API"):
            await api_wrapper.get_departures("AMS")

    @pytest.mark.asyncio
    async def test_get_disruptions_invalid_keyword(self, api_wrapper, mock_hass):
        """Test get_disruptions with auth error based on 'invalid' keyword."""
        mock_hass.async_add_executor_job.side_effect = ValueError("token invalid")

        with pytest.raises(NSAPIAuthError, match="Invalid API key"):
            await api_wrapper.get_disruptions()

    @pytest.mark.asyncio
    async def test_get_disruptions_timeout_error(self, api_wrapper, mock_hass):
        """Test get_disruptions with timeout error."""
        mock_hass.async_add_executor_job.side_effect = TimeoutError("Request timeout")

        with pytest.raises(NSAPIConnectionError, match="Failed to connect to NS API"):
            await api_wrapper.get_disruptions()

    def test_build_station_mapping_invalid_code_format(self, api_wrapper):
        """Test build_station_mapping with invalid station code formats."""
        stations = [
            "A" * 11 + " Station Name",  # Code too long (> 10 chars)
            "123*&# Station",  # Non-alphanumeric code
            "AMS " + "N" * 101,  # Name too long (> 100 chars)
        ]
        mapping = api_wrapper.build_station_mapping(stations)

        # Should skip all invalid formats
        assert mapping == {}

    def test_build_station_mapping_attribute_error_handling(self, api_wrapper):
        """Test build_station_mapping handles AttributeError gracefully."""
        # Create a station object that raises AttributeError when accessing attributes
        bad_station = MagicMock()
        bad_station.code = property(lambda self: self.nonexistent)

        stations = [bad_station]
        mapping = api_wrapper.build_station_mapping(stations)

        # Should skip the bad station
        assert mapping == {}

    def test_build_station_mapping_type_error_handling(self, api_wrapper):
        """Test build_station_mapping handles TypeError gracefully."""

        # Create a station that causes TypeError
        def bad_str():
            raise TypeError("Cannot convert to string")

        bad_station = MagicMock()
        bad_station.__str__ = bad_str

        stations = [bad_station]
        mapping = api_wrapper.build_station_mapping(stations)

        # Should skip the bad station
        assert mapping == {}

    def test_build_station_mapping_malformed_wrapper_no_space(self, api_wrapper):
        """Test build_station_mapping with malformed class wrapper (no space)."""
        stations = ["<Station>NoSpace"]
        mapping = api_wrapper.build_station_mapping(stations)

        # Should skip malformed format
        assert mapping == {}

    def test_build_station_mapping_code_name_type_validation(self, api_wrapper):
        """Test build_station_mapping validates code and name are strings."""
        # Create station with non-string code and name
        station = MagicMock()
        station.code = 123  # Not a string
        station.name = 456  # Not a string

        stations = [station]
        mapping = api_wrapper.build_station_mapping(stations)

        # Should skip station with non-string code/name
        assert mapping == {}

    def test_build_station_mapping_empty_code_handling(self, api_wrapper):
        """Test build_station_mapping with empty codes."""
        stations = [
            "",  # Empty string
            "   ",  # Only spaces
        ]
        mapping = api_wrapper.build_station_mapping(stations)

        # Should skip stations with empty codes
        assert mapping == {}

    @pytest.mark.asyncio
    async def test_get_trips_http_error_as_exception(self, api_wrapper, mock_hass):
        """Test get_trips with HTTP error caught as Exception."""
        http_error = HTTPError("Network error")
        mock_hass.async_add_executor_job.side_effect = http_error

        with pytest.raises(NSAPIError, match="Unexpected error getting trips"):
            await api_wrapper.get_trips("AMS", "UTR")

    @pytest.mark.asyncio
    async def test_get_departures_http_error_as_exception(self, api_wrapper, mock_hass):
        """Test get_departures with HTTP error caught as Exception."""
        http_error = HTTPError("Network error")
        mock_hass.async_add_executor_job.side_effect = http_error

        with pytest.raises(NSAPIError, match="Unexpected error getting departures"):
            await api_wrapper.get_departures("AMS")

    @pytest.mark.asyncio
    async def test_get_disruptions_http_error_as_exception(
        self, api_wrapper, mock_hass
    ):
        """Test get_disruptions with HTTP error caught as Exception."""
        http_error = HTTPError("Network error")
        mock_hass.async_add_executor_job.side_effect = http_error

        with pytest.raises(NSAPIError, match="Unexpected error getting disruptions"):
            await api_wrapper.get_disruptions()
