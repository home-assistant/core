"""Test LastFM component setup process."""

from homeassistant.components.lastfm.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
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


async def test_setup_retry_when_no_user_data(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    config_entry: MockConfigEntry,
    not_found_user: MockUser,
) -> None:
    """Test setup is retried when no user data could be fetched."""
    await setup_integration(config_entry, not_found_user)

    assert config_entry.state is ConfigEntryState.SETUP_RETRY
    assert config_entry.error_reason_translation_key == "update_failed"
    assert (
        config_entry.reason
        == "Could not retrieve data from Last.fm for any of the configured users"
    )
