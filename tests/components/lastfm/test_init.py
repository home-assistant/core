"""Test LastFM component setup process."""
from __future__ import annotations

from homeassistant.components.lastfm.const import DOMAIN
from homeassistant.core import HomeAssistant

from . import MockUser
from .conftest import ComponentSetup

from tests.common import MockConfigEntry


async def test_load_unload_entry(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    config_entry: MockConfigEntry,
    default_user: MockUser,
) -> None:
    """Test load and unload entry."""
    await setup_integration(config_entry, default_user)
    entry = hass.config_entries.async_entries(DOMAIN)[0]

    state = hass.states.get("sensor.lastfm_testaccount1")
    assert state

    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.lastfm_testaccount1")
    assert not state
