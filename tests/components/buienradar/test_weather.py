"""The tests for the buienradar weather component."""
from homeassistant.components import weather
from homeassistant.setup import async_setup_component

# Example config snippet from documentation.
BASE_CONFIG = {
    "weather": [
        {
            "platform": "buienradar",
            "name": "volkel",
            "latitude": 51.65,
            "longitude": 5.7,
            "forecast": True,
        }
    ]
}


async def test_smoke_test_setup_component(hass):
    """Smoke test for successfully set-up with default config."""
    assert await async_setup_component(hass, weather.DOMAIN, BASE_CONFIG)
    await hass.async_block_till_done()

    state = hass.states.get("weather.volkel")
    assert state.state == "unknown"
