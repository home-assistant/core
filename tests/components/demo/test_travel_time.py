"""Test the travel_time integration."""
from homeassistant.components.travel_time import DOMAIN
from homeassistant.const import EVENT_HOMEASSISTANT_START
from homeassistant.setup import async_setup_component


async def test_travel_time(hass):
    """Test the travel time component."""
    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: {
                "platform": "demo",
                "name": "demo",
                "origin_name": "Democity",
                "destination_name": "Destinationcity",
                "travel_mode": "car",
            }
        },
    )
    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()
    sensor = hass.states.get("travel_time.demo")
    assert int(sensor.state) >= 5
