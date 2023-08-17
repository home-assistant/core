"""Test fixtures for calendar sensor platforms."""
import pytest

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


@pytest.fixture(autouse=True)
async def setup_homeassistant(hass: HomeAssistant):
    """Set up the homeassistant integration."""
    await async_setup_component(hass, "homeassistant", {})


@pytest.fixture
def set_time_zone(hass: HomeAssistant) -> None:
    """Set the time zone for the tests."""
    # Set our timezone to CST/Regina so we can check calculations
    # This keeps UTC-6 all year round
    hass.config.set_time_zone("America/Regina")
