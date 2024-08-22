"""Test the Enigma2 integration init."""

from unittest.mock import patch

from homeassistant.components.enigma2.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import TEST_REQUIRED, MockDevice

from tests.common import MockConfigEntry


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test successful unload of entry."""
    with (
        patch(
            "homeassistant.components.enigma2.coordinator.OpenWebIfDevice.__new__",
            return_value=MockDevice(),
        ),
        patch(
            "homeassistant.components.enigma2.media_player.async_setup_entry",
            return_value=True,
        ),
    ):
        entry = MockConfigEntry(domain=DOMAIN, data=TEST_REQUIRED, title="name")
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.data.get(DOMAIN)
