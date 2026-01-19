"""Tests for the Nina integration."""

from copy import deepcopy
from unittest.mock import AsyncMock

from pynina import Warning

from homeassistant.components.nina.const import CONF_REGIONS
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def setup_platform(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_nina_class: AsyncMock,
    nina_warnings: list[Warning],
) -> None:
    """Set up the NINA platform."""
    mock_nina_class.warnings = {
        region: deepcopy(nina_warnings)
        for region in config_entry.data.get(CONF_REGIONS, {})
    }

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
