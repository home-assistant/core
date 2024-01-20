"""Tests for the Teslemetry integration."""

from unittest.mock import patch

from homeassistant.components.teslemetry.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import CONFIG

from tests.common import MockConfigEntry


async def setup_platform(
    hass: HomeAssistant, platforms: list[Platform] = [], side_effect=None
):
    """Set up the Teslemetry platform."""

    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG,
    )
    mock_entry.add_to_hass(hass)

    with patch("homeassistant.components.teslemetry.PLATFORMS", platforms):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    return mock_entry
