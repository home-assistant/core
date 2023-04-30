"""Test LastFM component setup process."""
from __future__ import annotations

from homeassistant.components.lastfm.const import CONF_USERS, DOMAIN
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant

from . import patch_fetch_user

from tests.common import MockConfigEntry


async def test_load_unload_entry(hass: HomeAssistant) -> None:
    """Test load and unload entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "12345678", CONF_USERS: ["test"]},
    )
    entry.add_to_hass(hass)
    with patch_fetch_user():
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.lastfm_test")
    assert state

    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.lastfm_test")
    assert not state
