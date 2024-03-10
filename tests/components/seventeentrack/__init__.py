"""Tests for the seventeentrack component."""

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.seventeentrack.sensor import DEFAULT_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
from homeassistant.setup import async_setup_component

from tests.common import async_fire_time_changed


async def init_integration(hass: HomeAssistant, config: ConfigType):
    """Set up the seventeentrack integration in Home Assistant."""
    assert await async_setup_component(hass, "sensor", config)
    await hass.async_block_till_done()


async def goto_future(hass: HomeAssistant, freezer: FrozenDateTimeFactory):
    """Move to future."""
    freezer.tick(DEFAULT_SCAN_INTERVAL + timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
