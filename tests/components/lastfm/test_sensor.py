"""Tests for the lastfm sensor."""
from unittest.mock import patch

from homeassistant.components import sensor
from homeassistant.components.lastfm.const import STATE_NOT_SCROBBLING
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import MockLastFMNetwork, MockUser

from tests.components.lastfm import MOCK_TRACK

CONFIG = {
    "sensor": {
        "platform": "lastfm",
        "api_key": "secret-key",
        "users": ["test"],
    }
}


async def test_update_not_playing(hass: HomeAssistant) -> None:
    """Test update when no playing song."""
    with patch(
        "homeassistant.components.lastfm.coordinator.LastFMNetwork",
        return_value=MockLastFMNetwork(MockUser()),
    ):
        assert await async_setup_component(hass, sensor.DOMAIN, CONFIG) is True
        await hass.async_block_till_done()

    entity_id = "sensor.lastfm_test"

    state = hass.states.get(entity_id)

    assert state.state == STATE_NOT_SCROBBLING


async def test_update_playing(hass: HomeAssistant) -> None:
    """Test update when song playing."""
    with patch(
        "homeassistant.components.lastfm.coordinator.LastFMNetwork",
        return_value=MockLastFMNetwork(MockUser(MOCK_TRACK)),
    ):
        assert await async_setup_component(hass, sensor.DOMAIN, CONFIG) is True
        await hass.async_block_till_done()

    entity_id = "sensor.lastfm_test"

    state = hass.states.get(entity_id)

    assert state.state == "Goldband - Noodgeval"


async def test_failed_update(hass: HomeAssistant) -> None:
    """Test that the integration does not break when an unknown user is added."""
    with patch(
        "homeassistant.components.lastfm.coordinator.LastFMNetwork",
        return_value=MockLastFMNetwork(MockUser(MOCK_TRACK)),
    ):
        assert (
            await async_setup_component(
                hass,
                sensor.DOMAIN,
                {
                    "sensor": {
                        "platform": "lastfm",
                        "api_key": "secret-key",
                        "users": ["not_existing"],
                    }
                },
            )
            is True
        )
        await hass.async_block_till_done()

    entity_id = "sensor.lastfm_not_existing"

    state = hass.states.get(entity_id)

    assert state.state == "unknown"
