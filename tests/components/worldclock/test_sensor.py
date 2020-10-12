"""The test for the World clock sensor platform."""
import pytest

from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util


@pytest.fixture
def time_zone():
    """Fixture for time zone."""
    return dt_util.get_time_zone("America/New_York")


async def test_time(hass, time_zone):
    """Test the time at a different location."""
    config = {"sensor": {"platform": "worldclock", "time_zone": "America/New_York"}}

    assert await async_setup_component(
        hass,
        "sensor",
        config,
    )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.worldclock_sensor")
    assert state is not None

    assert state.state == dt_util.now(time_zone=time_zone).strftime("%H:%M")


async def test_time_format(hass, time_zone):
    """Test time_format setting."""
    time_format = "%a, %b %d, %Y %I:%M %p"
    config = {
        "sensor": {
            "platform": "worldclock",
            "time_zone": "America/New_York",
            "time_format": time_format,
        }
    }

    assert await async_setup_component(
        hass,
        "sensor",
        config,
    )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.worldclock_sensor")
    assert state is not None

    assert state.state == dt_util.now(time_zone=time_zone).strftime(time_format)
