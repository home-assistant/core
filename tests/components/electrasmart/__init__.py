"""Tests for the Electra Air Conditioner integration."""

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
from pytest_homeassistant.common import async_fire_time_changed

from homeassistant.components.electrasmart.const import SCAN_INTERVAL_SEC
from homeassistant.core import HomeAssistant


async def async_advance_to_next_poll(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Let the coordinator poll the way it does on its own schedule."""
    freezer.tick(timedelta(seconds=SCAN_INTERVAL_SEC + 1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
