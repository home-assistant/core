"""Tests for Tibber sensor price interval functionality."""

from __future__ import annotations

import datetime as dt
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.tibber.const import (
    DEFAULT_PRICE_INTERVAL,
    PRICE_INTERVAL_15MIN,
    PRICE_INTERVAL_HOURLY,
    UPDATE_INTERVAL_15MIN,
    UPDATE_INTERVAL_HOURLY,
)
from homeassistant.components.tibber.sensor import TibberSensorElPrice
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util


@pytest.fixture
def mock_tibber_home():
    """Create a mock Tibber home for price interval tests."""
    home = AsyncMock()
    home.home_id = "test_home_id"
    home.currency = "NOK"
    home.price_unit = "NOK/kWh"
    home.price_total = 1.5
    home.last_data_timestamp = dt_util.now()

    # Mock price data
    now = dt_util.now()
    home.price_info_today = [
        {
            "startsAt": now.isoformat(),
            "total": 1.5,
            "level": "NORMAL",
        },
        {
            "startsAt": (now + dt.timedelta(hours=1)).isoformat(),
            "total": 2.0,
            "level": "HIGH",
        },
    ]

    home.current_price_data = MagicMock(return_value=(1.5, now, "NORMAL"))
    home.current_attributes = MagicMock(
        return_value={
            "max_price": 2.0,
            "avg_price": 1.5,
            "min_price": 1.0,
        }
    )
    home.update_info_and_price_info = AsyncMock()

    return home


class TestTibberSensorPriceIntervals:
    """Test price interval functionality in TibberSensorElPrice."""

    def test_get_update_interval_minutes_hourly(self, mock_tibber_home):
        """Test update interval for hourly price interval."""
        sensor = TibberSensorElPrice(mock_tibber_home)
        interval_minutes = sensor._get_update_interval_minutes(PRICE_INTERVAL_HOURLY)
        assert interval_minutes == UPDATE_INTERVAL_HOURLY

    def test_get_update_interval_minutes_15min(self, mock_tibber_home):
        """Test update interval for 15-minute price interval."""
        sensor = TibberSensorElPrice(mock_tibber_home)
        interval_minutes = sensor._get_update_interval_minutes(PRICE_INTERVAL_15MIN)
        assert interval_minutes == UPDATE_INTERVAL_15MIN

    def test_get_update_interval_minutes_invalid(self, mock_tibber_home):
        """Test update interval for invalid price interval defaults to hourly."""
        sensor = TibberSensorElPrice(mock_tibber_home)
        interval_minutes = sensor._get_update_interval_minutes("invalid_interval")
        assert interval_minutes == UPDATE_INTERVAL_HOURLY

    def test_get_price_data_by_interval_hourly(self, mock_tibber_home):
        """Test getting price data for hourly interval."""
        sensor = TibberSensorElPrice(mock_tibber_home)
        price_data = sensor._get_price_data_by_interval(PRICE_INTERVAL_HOURLY)
        assert len(price_data) == 2
        assert price_data[0]["total"] == 1.5

    def test_get_price_data_by_interval_15min(self, mock_tibber_home):
        """Test getting price data for 15-minute interval."""
        sensor = TibberSensorElPrice(mock_tibber_home)
        price_data = sensor._get_price_data_by_interval(PRICE_INTERVAL_15MIN)
        assert len(price_data) == 8  # 4 intervals per hour * 2 hours
        assert price_data[0]["total"] == 1.5

    def test_get_15min_price_data_empty_hourly_data(self, mock_tibber_home):
        """Test 15-minute price data generation with empty hourly data."""
        sensor = TibberSensorElPrice(mock_tibber_home)
        mock_tibber_home.price_info_today = []
        mock_tibber_home.current_price_data = MagicMock(return_value=(None, None, None))
        price_data = sensor._get_15min_price_data()
        assert price_data == []

    def test_find_current_price_hourly_interval(self, mock_tibber_home):
        """Test finding current price with hourly interval."""
        sensor = TibberSensorElPrice(mock_tibber_home)
        now = dt_util.now()
        price_data = [
            {
                "startsAt": (now - dt.timedelta(minutes=30)).isoformat(),
                "total": 1.5,
                "level": "NORMAL",
            }
        ]
        current_price = sensor._find_current_price(
            price_data, now, PRICE_INTERVAL_HOURLY
        )
        assert current_price is not None
        assert current_price["total"] == 1.5

    def test_find_current_price_empty_data(self, mock_tibber_home):
        """Test finding current price with empty price data."""
        sensor = TibberSensorElPrice(mock_tibber_home)
        now = dt_util.now()
        current_price = sensor._find_current_price([], now, PRICE_INTERVAL_HOURLY)
        assert current_price is None

    async def test_async_update_default_interval(
        self, hass: HomeAssistant, mock_tibber_home
    ):
        """Test async_update uses default interval when no input_select exists."""
        sensor = TibberSensorElPrice(mock_tibber_home)
        sensor.hass = hass

        with patch.object(sensor, "_fetch_data", return_value=True):
            await sensor.async_update()

        assert (
            sensor._attr_extra_state_attributes["price_interval"]
            == DEFAULT_PRICE_INTERVAL
        )

    async def test_async_update_with_input_select_hourly(
        self, hass: HomeAssistant, mock_tibber_home
    ):
        """Test async_update uses hourly interval from input_select."""
        sensor = TibberSensorElPrice(mock_tibber_home)
        sensor.hass = hass
        hass.states.async_set(
            "input_select.tibber_price_interval", PRICE_INTERVAL_HOURLY
        )

        with patch.object(sensor, "_fetch_data", return_value=True):
            await sensor.async_update()

        assert (
            sensor._attr_extra_state_attributes["price_interval"]
            == PRICE_INTERVAL_HOURLY
        )

    async def test_async_update_with_input_select_15min(
        self, hass: HomeAssistant, mock_tibber_home
    ):
        """Test async_update uses 15-minute interval from input_select."""
        sensor = TibberSensorElPrice(mock_tibber_home)
        sensor.hass = hass
        hass.states.async_set(
            "input_select.tibber_price_interval", PRICE_INTERVAL_15MIN
        )

        with patch.object(sensor, "_fetch_data", return_value=True):
            await sensor.async_update()

        assert (
            sensor._attr_extra_state_attributes["price_interval"]
            == PRICE_INTERVAL_15MIN
        )

    async def test_async_update_stores_price_arrays(
        self, hass: HomeAssistant, mock_tibber_home
    ):
        """Test that async_update stores both hourly and 15-minute price arrays."""
        sensor = TibberSensorElPrice(mock_tibber_home)
        sensor.hass = hass

        with patch.object(sensor, "_fetch_data", return_value=True):
            await sensor.async_update()

        assert "prices_1h" in sensor._attr_extra_state_attributes
        assert "prices_15min" in sensor._attr_extra_state_attributes
        assert len(sensor._attr_extra_state_attributes["prices_1h"]) == 2
        assert len(sensor._attr_extra_state_attributes["prices_15min"]) == 8

    def test_should_skip_update_logic(self, mock_tibber_home):
        """Test skip update logic with different intervals."""
        sensor = TibberSensorElPrice(mock_tibber_home)
        now = dt_util.now()
        sensor._last_updated = now - dt.timedelta(minutes=30)
        sensor._tibber_home.price_total = 1.5
        sensor._tibber_home.last_data_timestamp = now

        # Should skip with 60-minute interval (30 < 60)
        assert sensor._should_skip_update(now, 60) is True
        # Should not skip with 15-minute interval (30 > 15)
        assert sensor._should_skip_update(now, 15) is False

    async def test_async_update_skip_logic_integration(
        self, hass: HomeAssistant, mock_tibber_home
    ):
        """Test that price interval affects update skip logic."""
        sensor = TibberSensorElPrice(mock_tibber_home)
        sensor.hass = hass

        now = dt_util.now()
        mock_tibber_home.price_total = 1.5
        mock_tibber_home.last_data_timestamp = now - dt.timedelta(hours=1)
        sensor._last_updated = now - dt.timedelta(minutes=30)
        hass.states.async_set(
            "input_select.tibber_price_interval", PRICE_INTERVAL_HOURLY
        )

        with patch.object(sensor, "_fetch_data", return_value=True) as mock_fetch:
            await sensor.async_update()

        # Should skip because 30 min < 60 min interval
        mock_fetch.assert_not_called()

    async def test_async_update_no_skip_with_old_data(
        self, hass: HomeAssistant, mock_tibber_home
    ):
        """Test that old data triggers fetch regardless of interval."""
        sensor = TibberSensorElPrice(mock_tibber_home)
        sensor.hass = hass

        now = dt_util.now()
        mock_tibber_home.price_total = 1.5
        mock_tibber_home.last_data_timestamp = now - dt.timedelta(
            hours=11
        )  # Very old data
        sensor._last_updated = now - dt.timedelta(minutes=30)
        hass.states.async_set(
            "input_select.tibber_price_interval", PRICE_INTERVAL_HOURLY
        )

        with patch.object(sensor, "_fetch_data", return_value=True) as mock_fetch:
            await sensor.async_update()

        # Should fetch because data is too old
        mock_fetch.assert_called_once()

    def test_find_current_price_15min_interval(self, mock_tibber_home):
        """Test finding current price with 15-minute interval."""
        sensor = TibberSensorElPrice(mock_tibber_home)
        now = dt_util.now()
        price_data = [
            {
                "startsAt": (now - dt.timedelta(minutes=10)).isoformat(),
                "total": 1.8,
                "level": "HIGH",
            }
        ]
        current_price = sensor._find_current_price(
            price_data, now, PRICE_INTERVAL_15MIN
        )
        assert current_price is not None
        assert current_price["total"] == 1.8
        assert current_price["level"] == "HIGH"

    def test_find_current_price_no_match(self, mock_tibber_home):
        """Test finding current price when no price matches current time."""
        sensor = TibberSensorElPrice(mock_tibber_home)
        now = dt_util.now()
        price_data = [
            {
                "startsAt": (now + dt.timedelta(hours=1)).isoformat(),
                "total": 1.5,
                "level": "NORMAL",
            }
        ]
        current_price = sensor._find_current_price(
            price_data, now, PRICE_INTERVAL_HOURLY
        )
        assert current_price is None

    def test_get_15min_price_data_timing_validation(self, mock_tibber_home):
        """Test that 15-minute intervals are correctly timed."""
        sensor = TibberSensorElPrice(mock_tibber_home)
        price_data = sensor._get_15min_price_data()

        # Check that intervals are 15 minutes apart
        for i in range(1, len(price_data)):
            prev_time = dt_util.parse_datetime(price_data[i - 1]["startsAt"])
            curr_time = dt_util.parse_datetime(price_data[i]["startsAt"])
            time_diff = (curr_time - prev_time).total_seconds()
            assert time_diff == 15 * 60  # 15 minutes in seconds

    async def test_async_update_with_invalid_input_select(
        self, hass: HomeAssistant, mock_tibber_home
    ):
        """Test async_update ignores invalid input_select value."""
        sensor = TibberSensorElPrice(mock_tibber_home)
        sensor.hass = hass

        # Set up input_select state with invalid value
        hass.states.async_set("input_select.tibber_price_interval", "invalid_interval")

        with patch.object(sensor, "_fetch_data", return_value=True):
            await sensor.async_update()

        assert (
            sensor._attr_extra_state_attributes["price_interval"]
            == DEFAULT_PRICE_INTERVAL
        )

    def test_should_skip_update_edge_cases(self, mock_tibber_home):
        """Test skip update logic with edge cases."""
        sensor = TibberSensorElPrice(mock_tibber_home)
        now = dt_util.now()

        # Test with missing conditions - should not skip
        assert not sensor._should_skip_update(now, 60)

        # Test with future last_updated - should not skip
        sensor._last_updated = now + dt.timedelta(minutes=10)
        sensor._tibber_home.price_total = 1.5
        sensor._tibber_home.last_data_timestamp = now
        assert not sensor._should_skip_update(now, 60)

        # Test with exactly at interval boundary
        sensor._last_updated = now - dt.timedelta(minutes=60)
        assert not sensor._should_skip_update(now, 60)

    def test_get_hourly_price_data_fallback(self, mock_tibber_home):
        """Test hourly price data fallback to current_price_data."""
        sensor = TibberSensorElPrice(mock_tibber_home)

        # Test fallback when price_info_today is None
        mock_tibber_home.price_info_today = None
        mock_tibber_home.current_price_data.return_value = (2.5, dt_util.now(), "HIGH")

        data = sensor._get_hourly_price_data()
        assert len(data) == 1
        assert data[0]["total"] == 2.5
        assert data[0]["level"] == "HIGH"

    def test_get_hourly_price_data_no_fallback(self, mock_tibber_home):
        """Test hourly price data when no data available."""
        sensor = TibberSensorElPrice(mock_tibber_home)

        # Test when both price_info_today and current_price_data fail
        mock_tibber_home.price_info_today = None
        mock_tibber_home.current_price_data.return_value = (None, None, None)

        data = sensor._get_hourly_price_data()
        assert data == []

    def test_get_15min_price_data_invalid_datetime(self, mock_tibber_home):
        """Test 15-minute price data with invalid datetime."""
        sensor = TibberSensorElPrice(mock_tibber_home)
        mock_tibber_home.price_info_today = [
            {
                "startsAt": "invalid_datetime",
                "total": 1.5,
                "level": "NORMAL",
            }
        ]

        data = sensor._get_15min_price_data()
        assert data == []

    async def test_async_update_fallback_price(
        self, hass: HomeAssistant, mock_tibber_home
    ):
        """Test async_update fallback to current_price_data when no specific price found."""
        sensor = TibberSensorElPrice(mock_tibber_home)
        sensor.hass = hass

        # Mock _find_current_price to return None (no specific price found)
        with (
            patch.object(sensor, "_fetch_data", return_value=True),
            patch.object(sensor, "_find_current_price", return_value=None),
        ):
            await sensor.async_update()

        # Should fallback to current_price_data
        assert sensor._attr_native_value == 1.5
        assert sensor._attr_extra_state_attributes["intraday_price_ranking"] == "NORMAL"

    def test_find_current_price_invalid_data(self, mock_tibber_home):
        """Test finding current price with invalid price data."""
        sensor = TibberSensorElPrice(mock_tibber_home)
        now = dt_util.now()

        # Test with invalid startsAt format
        price_data = [
            {
                "startsAt": "invalid_date",
                "total": 1.5,
                "level": "NORMAL",
            }
        ]

        current_price = sensor._find_current_price(
            price_data, now, PRICE_INTERVAL_HOURLY
        )
        assert current_price is None
