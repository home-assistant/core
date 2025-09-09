"""Tests for the quantum_gateway component."""

from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER_DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_PLATFORM
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


async def setup_platform(hass: HomeAssistant) -> None:
    """Set up the quantum_gateway integration."""
    result = await async_setup_component(
        hass,
        DEVICE_TRACKER_DOMAIN,
        {
            DEVICE_TRACKER_DOMAIN: {
                CONF_PLATFORM: "quantum_gateway",
                CONF_PASSWORD: "fake_password",
            }
        },
    )
    await hass.async_block_till_done()
    assert result
