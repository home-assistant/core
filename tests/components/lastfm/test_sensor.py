"""Tests for the lastfm sensor."""
from unittest.mock import patch

import pytest

from homeassistant.components import sensor
from homeassistant.components.lastfm.const import STATE_NOT_SCROBBLING
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import MockUser

from tests.components.lastfm import MOCK_TRACK


@pytest.fixture(name="lastfm_network")
def lastfm_network_fixture():
    """Create fixture for LastFMNetwork."""
    with patch("pylast.LastFMNetwork") as lastfm_network:
        yield lastfm_network


async def test_update_not_playing(hass: HomeAssistant, lastfm_network) -> None:
    """Test update when no playing song."""
    lastfm_network.return_value.get_user.return_value = MockUser()
    assert await async_setup_component(
        hass,
        sensor.DOMAIN,
        {
            "sensor": {
                "platform": "lastfm",
                "api_key": "secret-key",
                "users": ["test"],
            }
        },
    )
    await hass.async_block_till_done()

    entity_id = "sensor.test"

    state = hass.states.get(entity_id)

    assert state.state == STATE_NOT_SCROBBLING


async def test_update_playing(hass: HomeAssistant, lastfm_network) -> None:
    """Test update when song playing."""
    lastfm_network.return_value.get_user.return_value = MockUser(MOCK_TRACK)
    assert await async_setup_component(
        hass,
        sensor.DOMAIN,
        {
            "sensor": {
                "platform": "lastfm",
                "api_key": "secret-key",
                "users": ["test"],
            }
        },
    )
    await hass.async_block_till_done()

    entity_id = "sensor.test"

    state = hass.states.get(entity_id)

    assert state.state == "Goldband - Noodgeval"
