"""Test evil genius labs init."""
import pytest

from homeassistant import config_entries
from homeassistant.components.evil_genius_labs import PLATFORMS
from homeassistant.core import HomeAssistant


@pytest.mark.parametrize("platforms", [PLATFORMS])
async def test_setup_unload_entry(
    hass: HomeAssistant, setup_evil_genius_labs, config_entry
) -> None:
    """Test setting up and unloading a config entry."""
    assert len(hass.states.async_entity_ids()) == 1
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    assert config_entry.state == config_entries.ConfigEntryState.NOT_LOADED
