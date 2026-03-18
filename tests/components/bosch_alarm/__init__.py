"""Tests for the Bosch Alarm component."""

from unittest.mock import AsyncMock

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def setup_integration(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Fixture for setting up the component."""
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


async def call_observable(hass: HomeAssistant, observable: AsyncMock) -> None:
    """Call the observable with the given event."""
    for callback in observable.attach.call_args_list:
        callback[0][0]()
    await hass.async_block_till_done()
