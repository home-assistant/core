"""The test for the random number sensor platform."""
from homeassistant.setup import async_setup_component


async def test_random_sensor(hass):
    """Test the Random number sensor."""
    config = {
        "sensor": {
            "platform": "random",
            "name": "test",
            "minimum": 10,
            "maximum": 20,
        }
    }

    assert await async_setup_component(
        hass,
        "sensor",
        config,
    )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test")

    assert int(state.state) <= config["sensor"]["maximum"]
    assert int(state.state) >= config["sensor"]["minimum"]
