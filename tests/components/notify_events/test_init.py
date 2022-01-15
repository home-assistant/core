"""The tests for notify_events."""
from homeassistant.components.notify_events.const import DOMAIN
from homeassistant.setup import async_setup_component


async def test_setup(hass):
    """Test setup of the integration."""
    config = {"notify_events": {"token": "ABC"}}
    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()

    assert DOMAIN in hass.data
