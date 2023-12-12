"""Tests for sensor."""
from datetime import timedelta
from unittest.mock import patch
from homeassistant.components.krisinformation.const import (
    DOMAIN,
    DEFAULT_NAME,
    COUNTY_CODES,
)
from homeassistant.const import CONF_SCAN_INTERVAL, EVENT_HOMEASSISTANT_START, UnitOfLength
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from .const import (
    MOCK_CONFIG,
    FAKE_LANGUAGE,
)
from tests.common import MockConfigEntry, async_fire_time_changed

# Constants for the tests
TEST_HEADLINE = "Test Alert"
TEST_LATITUDE = 55.6761
TEST_LONGITUDE = 12.5683
TEST_COUNTY_CODE = COUNTY_CODES["17"]  # Replace with actual code
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=120)  # Adjust as per your sensor's update interval

async def test_successful_setup(hass: HomeAssistant) -> None:
    """Test successful setup of sensor."""
    with patch(
        "homeassistant.components.krisinformation.sensor.CrisisAlerterSensor.update",
        return_value=None,
    ):
        assert await async_setup_component(hass, DOMAIN, MOCK_CONFIG)
        await hass.async_block_till_done()

async def test_no_alarms_state(hass: HomeAssistant) -> None:
    """Test the state when there are no alarms."""
    with patch(
        "krisinformation.crisis_alerter.CrisisAlerter.vmas",
        return_value=[],
    ):
        await async_setup_component(hass, DOMAIN, MOCK_CONFIG)
        await hass.async_block_till_done()
        entity = hass.states.get(f"{DOMAIN}.{DEFAULT_NAME}_sweden")
        assert entity is not None
        assert entity.state == "No alarms"

async def test_alarms_state(hass: HomeAssistant) -> None:
    """Test the state when there are alarms."""
    mock_feed_entry = _generate_mock_feed_entry(TEST_HEADLINE, TEST_LATITUDE, TEST_LONGITUDE)
    with patch(
        "krisinformation.CrisisAlerter.vmas",
        return_value=[mock_feed_entry],
    ):
        await async_setup_component(hass, DOMAIN, MOCK_CONFIG)
        await hass.async_block_till_done()
        entity = hass.states.get(f"{DOMAIN}.{DEFAULT_NAME}_sweden")
        assert entity is not None
        assert entity.state == TEST_HEADLINE

async def test_error_state(hass: HomeAssistant) -> None:
    """Test the state when there is an error fetching data."""
    with patch(
        "krisinformation.CrisisAlerter.vmas",
        side_effect=Error("Test error"),
    ):
        await async_setup_component(hass, DOMAIN, MOCK_CONFIG)
        await hass.async_block_till_done()
        entity = hass.states.get(f"{DOMAIN}.{DEFAULT_NAME}_sweden")
        assert entity is not None
        assert entity.state == "Unavailable"

async def test_update_interval(hass: HomeAssistant) -> None:
    """Test that the sensor updates at the expected interval."""
    start_time = hass.loop.time()
    with patch(
        "krisinformation.CrisisAlerter.vmas",
        return_value=[],
    ):
        await async_setup_component(hass, DOMAIN, MOCK_CONFIG)
        await hass.async_block_till_done()
        entity = hass.states.get(f"{DOMAIN}.{DEFAULT_NAME}_sweden")
        assert entity is not None

        # Simulate passage of time
        async_fire_time_changed(hass, start_time + MIN_TIME_BETWEEN_UPDATES.total_seconds())
        await hass.async_block_till_done()

        # The sensor should have updated
        assert entity.state == "No alarms"