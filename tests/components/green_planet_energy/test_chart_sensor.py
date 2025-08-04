"""Test the chart sensor specifically."""

import pytest

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("init_integration")
async def test_chart_sensor_tomorrow_data(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test that the chart sensor includes tomorrow's data."""
    # Get the chart sensor
    chart_sensor = hass.states.get("sensor.gpe_price_chart_24h")
    assert chart_sensor is not None

    # Check that chart_data is populated
    chart_data = chart_sensor.attributes.get("chart_data", [])
    assert len(chart_data) == 24  # Should have 24 hours of data

    # Verify we have both today and tomorrow data
    today_count = sum(1 for item in chart_data if item.get("day") == "today")
    tomorrow_count = sum(1 for item in chart_data if item.get("day") == "tomorrow")

    # Should have data from both days (depends on current hour)
    assert today_count + tomorrow_count == 24
    assert tomorrow_count > 0  # Should have some tomorrow data

    # Verify prices are set (not None)
    prices = [item.get("price") for item in chart_data]
    valid_prices = [p for p in prices if p is not None]
    assert len(valid_prices) > 0  # Should have at least some valid prices


@pytest.mark.usefixtures("init_integration")
async def test_coordinator_tomorrow_data(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test that the coordinator has tomorrow's price data."""
    # Get the coordinator from runtime_data
    coordinator = init_integration.runtime_data

    # Check that we have both today and tomorrow data
    assert coordinator.data is not None

    # Check for today's data
    today_keys = [
        key
        for key in coordinator.data
        if key.startswith("gpe_price_") and not key.endswith("_tomorrow")
    ]
    assert len(today_keys) == 24  # Should have 24 hours for today

    # Check for tomorrow's data
    tomorrow_keys = [key for key in coordinator.data if key.endswith("_tomorrow")]
    assert len(tomorrow_keys) == 24  # Should have 24 hours for tomorrow

    # Verify some specific values (using the mock data values)
    assert coordinator.data.get("gpe_price_00") == 0.20  # Today's midnight price
    assert (
        coordinator.data.get("gpe_price_00_tomorrow") == 0.25
    )  # Tomorrow's midnight price
