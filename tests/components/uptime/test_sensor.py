"""The tests for the uptime sensor platform."""

from homeassistant.setup import async_setup_component


async def test_uptime_sensor_name_change(hass):
    """Test uptime sensor with different name."""
    config = {"sensor": {"platform": "uptime", "name": "foobar"}}
    assert await async_setup_component(hass, "sensor", config)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.foobar")
