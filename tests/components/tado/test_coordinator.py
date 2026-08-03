"""Test the Tado coordinator."""

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.tado import DOMAIN
from homeassistant.components.tado.coordinator import SCAN_INTERVAL
from homeassistant.core import HomeAssistant

from tests.common import async_fire_time_changed


@pytest.mark.usefixtures("init_integration")
async def test_update_interval_uses_remaining_calls(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test the update interval is derived from the remaining call budget."""
    coordinator = hass.config_entries.async_entries(DOMAIN)[0].runtime_data

    # 06:31 Europe/Berlin, so the daily reset is 5h29m away. With six zones a
    # cycle costs 9 + 6 calls and a 10% buffer is kept, so 100 remaining calls
    # give 19740 * 15 / 90 = 3290 seconds.
    freezer.move_to("2026-01-15 05:00:00+00:00")
    freezer.tick(timedelta(minutes=31))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert coordinator.update_interval == timedelta(seconds=3290)
    assert coordinator.update_interval > SCAN_INTERVAL
