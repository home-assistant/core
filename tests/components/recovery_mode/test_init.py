"""Tests for the Recovery Mode integration."""
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import async_get_persistent_notifications


async def test_works(hass: HomeAssistant) -> None:
    """Test Recovery Mode works."""
    assert await async_setup_component(hass, "recovery_mode", {})
    await hass.async_block_till_done()
    notifications = async_get_persistent_notifications(hass)
    assert len(notifications) == 1
