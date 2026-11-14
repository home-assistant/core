"""Tests for the Danfoss Air integration."""

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.danfoss_air import DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import async_fire_time_changed

CONFIG = {DOMAIN: {CONF_HOST: "192.0.2.1"}}


async def setup_integration(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Set up the Danfoss Air integration from YAML and run the first poll."""
    assert await async_setup_component(hass, DOMAIN, CONFIG)
    await hass.async_block_till_done()

    # Switches are added without update_before_add, so their first state
    # only arrives with the first scheduled poll.
    freezer.tick(timedelta(seconds=31))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
