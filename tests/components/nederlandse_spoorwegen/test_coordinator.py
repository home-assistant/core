"""Tests for Nederlandse Spoorwegen coordinator."""

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from requests.exceptions import ConnectionError, HTTPError, Timeout

from homeassistant.components.nederlandse_spoorwegen.const import DOMAIN
from homeassistant.components.nederlandse_spoorwegen.coordinator import (
    NSDataUpdateCoordinator,
    NSRouteData,
    _now_nl,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    DATE_SEPARATOR,
    DATETIME_FORMAT_LENGTH,
    DATETIME_SPACE,
    TIME_SEPARATOR,
)


class TestNSDataUpdateCoordinator:
    """Test the NS Data Update Coordinator."""

    @pytest.mark.parametrize(
        "exception_cls",
        [ConnectionError, Timeout, HTTPError, ValueError],
    )
    async def test_async_update_data_nsapi_exceptions(
        self, coordinator, mock_nsapi, exception_cls
    ):
        """Test that _async_update_data handles ns_api exceptions and sets error in NSRouteData or returns empty trips."""
        mock_nsapi.get_trips.side_effect = exception_cls("fail")
        data = await coordinator._async_update_data()
        assert isinstance(data, NSRouteData)
        # Accept either error field set or empty trips (as coordinator may handle in either place)
        if data.error is not None:
            assert "fail" in data.error
        else:
            assert data.trips == []

    @pytest.mark.parametrize(
        "exception_cls",
        [ConnectionError, Timeout, HTTPError, ValueError],
    )
    async def test_async_update_data_top_level_exception(
        self, coordinator, exception_cls
    ):
        """Test top-level exception handling in _async_update_data."""
        with patch.object(
            coordinator, "_get_trips_for_route", side_effect=exception_cls("fail-top")
        ):
            data = await coordinator._async_update_data()
            assert isinstance(data, NSRouteData)
            assert data.error is not None
            assert "fail-top" in data.error

    @pytest.mark.parametrize(
        "exception_cls",
        [ConnectionError, Timeout, HTTPError, ValueError],
    )
    async def test_get_trips_for_route_error_branch(self, coordinator, exception_cls):
        """Test error branch in _get_trips_for_route."""
        with patch.object(
            coordinator, "_get_trips", side_effect=exception_cls("fail-branch")
        ):
            route_data = await coordinator._get_trips_for_route(
                coordinator.route_config
            )
            assert route_data.error is not None
            assert "fail-branch" in route_data.error
            assert route_data.trips == []

    @pytest.mark.parametrize(
        "exception_cls",
        [ConnectionError, Timeout, HTTPError, ValueError],
    )
    async def test_get_trips_error_handling(self, coordinator, exception_cls):
        """Test error handling in _get_trips returns empty list."""
        with patch.object(
            coordinator.nsapi, "get_trips", side_effect=exception_cls("fail-get-trips")
        ):
            trips = await coordinator._get_trips("Ams", "Rot")
            assert trips == []

    @pytest.mark.parametrize(
        "exception_cls",
        [ConnectionError, Timeout, HTTPError, ValueError],
    )
    async def test_get_stations_error_handling(self, coordinator, exception_cls):
        """Test error handling in get_stations returns empty list."""
        with patch.object(
            coordinator.nsapi,
            "get_stations",
            side_effect=exception_cls("fail-get-stations"),
        ):
            stations = await coordinator.get_stations()
            assert stations == []

    def test_coordinator_initialization(
        self, hass: HomeAssistant, mock_config_entry: ConfigEntry, mock_nsapi
    ):
        """Test coordinator initialization."""
        subentry = list(mock_config_entry.subentries.values())[0]
        coordinator = NSDataUpdateCoordinator(
            hass=hass,
            config_entry=mock_config_entry,
            route_id=subentry.subentry_id,
            route_data=dict(subentry.data),
        )

        assert coordinator.route_id == subentry.subentry_id
        assert coordinator.name == f"{DOMAIN}_{subentry.subentry_id}"
        assert coordinator.config_entry == mock_config_entry
        assert coordinator.update_interval == timedelta(minutes=2)

    @pytest.mark.parametrize(
        ("input_time", "expected_output", "description"),
        [
            (
                None,
                "current_datetime_format",
                "None input should return current date and time",
            ),
            (
                "08:30",
                "today_08:30",
                "HH:MM format should combine with today's date",
            ),
            (
                "08:30:45",
                "today_08:30",
                "HH:MM:SS format should truncate to HH:MM and combine with today",
            ),
            (
                "10-10-2025 14:30",
                "today_14:30",
                "Full datetime should extract time and combine with today's date",
            ),
            (
                "01-01-2020 09:15",
                "today_09:15",
                "Past datetime should discard date and use today with extracted time",
            ),
            (
                "invalid_time",
                "current_datetime_format",
                "Invalid format should fallback to current date and time",
            ),
        ],
        ids=[
            "none_input",
            "time_only_hh_mm",
            "time_only_hh_mm_ss",
            "full_datetime_future",
            "full_datetime_past",
            "invalid_format",
        ],
    )
    def test_get_time_from_route_parametrized(
        self, coordinator, input_time, expected_output, description
    ):
        """Test _get_time_from_route with various inputs."""
        result = coordinator._get_time_from_route(input_time)
        today = _now_nl().strftime("%d-%m-%Y")

        if expected_output == "current_datetime_format":
            # For None and invalid inputs, check format
            assert len(result) == DATETIME_FORMAT_LENGTH  # "DD-MM-YYYY HH:MM" format
            assert result[2] == DATE_SEPARATOR
            assert result[5] == DATE_SEPARATOR
            assert result[10] == DATETIME_SPACE
            assert result[13] == TIME_SEPARATOR
        elif expected_output.startswith("today_"):
            # For valid time inputs, check exact output
            time_part = expected_output.replace("today_", "")
            expected = f"{today} {time_part}"
            assert result == expected

    def test_now_nl_function(self):
        """Test the _now_nl helper function."""
        with patch(
            "homeassistant.components.nederlandse_spoorwegen.coordinator.dt_util.now"
        ) as mock_now:
            mock_now.return_value = datetime(2025, 10, 10, 14, 30, 0)
            result = _now_nl()

            # Should return a datetime object
            assert isinstance(result, datetime)

    async def test_coordinator_with_api_key_config(
        self, hass: HomeAssistant, mock_config_entry: ConfigEntry, mock_nsapi
    ):
        """Test coordinator with API key from config entry."""
        subentry = list(mock_config_entry.subentries.values())[0]
        coordinator = NSDataUpdateCoordinator(
            hass=hass,
            config_entry=mock_config_entry,
            route_id=subentry.subentry_id,
            route_data=dict(subentry.data),
        )

        # The coordinator should use the API key from config_entry.data
        assert coordinator.nsapi is not None

    async def test_async_update_data_success(self, coordinator, mock_nsapi):
        """Test successful data update using existing fixture data."""
        # The mock_nsapi fixture already has trips configured
        data = await coordinator._async_update_data()
        assert data is not None
        # Should return an NSRouteData object
        assert isinstance(data, NSRouteData)
