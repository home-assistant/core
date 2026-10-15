"""Tests for the Sense integration."""

from datetime import timedelta
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.sense.const import DOMAIN, TREND_UPDATE_MINUTES
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed


async def setup_platform(
    hass: HomeAssistant, config_entry: MockConfigEntry, platform: Platform
) -> MockConfigEntry:
    """Set up the Sense platform."""
    config_entry.add_to_hass(hass)

    with patch("homeassistant.components.sense.PLATFORMS", [platform]):
        assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    return config_entry


async def trigger_trend_refresh(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Move the clock to the next phase-locked trend refresh and run it."""
    now = dt_util.utcnow()
    hour = now.replace(minute=0, second=0, microsecond=0)
    offsets = [hour + timedelta(minutes=minute) for minute in TREND_UPDATE_MINUTES]
    offsets.append(offsets[0] + timedelta(hours=1))
    freezer.move_to(next(offset for offset in offsets if offset > now))
    async_fire_time_changed(hass)
    # The time change listener runs the refresh as a background task.
    await hass.async_block_till_done(wait_background_tasks=True)
