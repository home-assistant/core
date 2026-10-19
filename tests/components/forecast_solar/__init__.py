"""Tests for the Forecast Solar integration."""

from freezegun.api import FrozenDateTimeFactory
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.core import HomeAssistant


async def async_next_update(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, entry: MockConfigEntry
) -> None:
    """Advance time to the entry's next scheduled forecast update."""
    freezer.tick(entry.runtime_data.update_interval)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
