"""Tests for RYSE init setup."""

import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Create a mock config entry for the RYSE integration."""
    return MockConfigEntry(
        domain="ryse",
        data={"address": "AA:BB:CC:DD:EE:FF"},
        title="Mock RYSE Device",
    )


async def test_setup_and_unload(
    hass: HomeAssistant,
) -> None:
    """Test integration setup and unload."""

    config_entry = MockConfigEntry(
        domain="ryse", title="Test Device", unique_id="AA:BB:CC:DD:EE:FF", data={}
    )

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.NOT_LOADED
