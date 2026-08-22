"""Test LastFM component setup process."""

from unittest.mock import patch

from pylast import LastFMNetwork

from homeassistant.components.lastfm.const import (
    CONF_API_SECRET,
    CONF_SESSION_KEY,
    DOMAIN,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import API_KEY, API_SECRET, SESSION_KEY, MockUser
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


async def test_load_entry_with_session_key(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    default_user: MockUser,
) -> None:
    """Test the client is authenticated with a session key when configured."""
    config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        config_entry,
        options={
            **config_entry.options,
            CONF_API_SECRET: API_SECRET,
            CONF_SESSION_KEY: SESSION_KEY,
        },
    )
    with (
        patch("pylast.User", return_value=default_user),
        patch(
            "homeassistant.components.lastfm.coordinator.LastFMNetwork",
            wraps=LastFMNetwork,
        ) as mock_network,
    ):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

    mock_network.assert_called_once_with(
        api_key=API_KEY, api_secret=API_SECRET, session_key=SESSION_KEY
    )
