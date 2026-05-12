"""Test the Zeversolar integration setup."""

from unittest.mock import patch

from zeversolar.exceptions import ZeverSolarTimeout

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import init_integration

from tests.common import MockConfigEntry


async def test_setup_retries_when_inverter_unreachable(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Entry enters SETUP_RETRY when the inverter cannot be reached."""
    config_entry.add_to_hass(hass)

    with patch("zeversolar.ZeverSolarClient.get_data", side_effect=ZeverSolarTimeout):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_and_unload(hass: HomeAssistant) -> None:
    """Entry loads successfully and can be unloaded."""
    entry = await init_integration(hass)
    assert entry.state is ConfigEntryState.LOADED

    result = await hass.config_entries.async_unload(entry.entry_id)
    assert result is True
    assert entry.state is ConfigEntryState.NOT_LOADED
