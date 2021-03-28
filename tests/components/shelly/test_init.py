"""Tests for the Shelly integration init."""
from homeassistant.components.shelly import async_services_setup
from homeassistant.components.shelly.const import DOMAIN, SERVICES


async def test_services_registered(hass, device_reg):
    """Test if all services are registered."""
    await async_services_setup(hass, device_reg)
    for service in SERVICES:
        assert hass.services.has_service(DOMAIN, service)
