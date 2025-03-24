"""Tests for the awair component."""

from unittest.mock import patch

from homeassistant.components.awair.const import DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def setup_awair(hass: HomeAssistant, fixtures, unique_id, data) -> ConfigEntry:
    """Add Awair devices to hass, using specified fixtures for data."""

    entry = MockConfigEntry(domain=DOMAIN, unique_id=unique_id, data=data)
    with patch("python_awair.AwairClient.query", side_effect=fixtures):
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry
