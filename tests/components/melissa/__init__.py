"""Tests for the melissa component."""

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

VALID_CONFIG = {"melissa": {"username": "********", "password": "********"}}


async def setup_integration(hass: HomeAssistant) -> None:
    """Set up the melissa integration in Home Assistant."""
    assert await async_setup_component(hass, "melissa", VALID_CONFIG)
    await hass.async_block_till_done()
