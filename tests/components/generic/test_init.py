"""Define tests for the generic (IP camera) integration."""

import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("fakeimg_png")
async def test_unload_entry(hass: HomeAssistant, setup_entry: MockConfigEntry) -> None:
    """Test unloading the generic IP Camera entry."""
    assert setup_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(setup_entry.entry_id)
    await hass.async_block_till_done()
    assert setup_entry.state is ConfigEntryState.NOT_LOADED


async def test_reload_on_title_change(
    hass: HomeAssistant, setup_entry: MockConfigEntry
) -> None:
    """Test the integration gets reloaded when the title is updated."""
    assert setup_entry.state is ConfigEntryState.LOADED
    assert (
        hass.states.get("camera.test_camera").attributes["friendly_name"]
        == "Test Camera"
    )

    hass.config_entries.async_update_entry(setup_entry, title="New Title")
    assert setup_entry.title == "New Title"
    await hass.async_block_till_done()

    assert (
        hass.states.get("camera.test_camera").attributes["friendly_name"] == "New Title"
    )
