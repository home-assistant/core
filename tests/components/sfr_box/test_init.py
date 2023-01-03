"""Test the SFR Box setup process."""
from unittest.mock import patch

import pytest
from sfrbox_api.exceptions import SFRBoxError

from homeassistant.components.sfr_box.const import DOMAIN
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant


@pytest.fixture(autouse=True)
def override_platforms():
    """Override PLATFORMS."""
    with patch("homeassistant.components.sfr_box.PLATFORMS", []):
        yield


@pytest.mark.usefixtures("system_get_info", "dsl_get_info")
async def test_setup_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    """Test entry setup and unload."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.entry_id in hass.data[DOMAIN]

    # Unload the entry and verify that the data has been removed
    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.NOT_LOADED
    assert config_entry.entry_id not in hass.data[DOMAIN]


async def test_setup_entry_exception(hass: HomeAssistant, config_entry: ConfigEntry):
    """Test ConfigEntryNotReady when API raises an exception during entry setup."""
    with patch(
        "homeassistant.components.sfr_box.coordinator.SFRBox.system_get_info",
        side_effect=SFRBoxError,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert config_entry.state is ConfigEntryState.SETUP_RETRY
    assert not hass.data.get(DOMAIN)
