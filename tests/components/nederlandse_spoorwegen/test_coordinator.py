"""Tests for Nederlandse Spoorwegen coordinator."""

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

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
