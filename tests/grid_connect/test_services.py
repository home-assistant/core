"""Tests for services in the Grid Connect integration."""

from homeassistant.setup import async_setup_component

DOMAIN = "grid_connect"

async def test_services_exist(hass):
    """Ensure custom services are registered."""
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()

    services = hass.services.async_services()
    assert DOMAIN in services
    assert "turn_on" in services[DOMAIN]
    assert "turn_off" in services[DOMAIN]

async def test_call_turn_on_off_services(hass):
    """Call turn_on and turn_off services without error."""
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()

    # Should not raise
    await hass.services.async_call(DOMAIN, "turn_on", {"entity_id": "light.test"}, blocking=True)
    await hass.services.async_call(DOMAIN, "turn_off", {"entity_id": "light.test"}, blocking=True)
