"""Tests for the lastfm sensor."""
from homeassistant.components import sensor
from homeassistant.components.lastfm.const import STATE_NOT_SCROBBLING
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.components.lastfm import MOCK_TRACK, patch_interface


async def test_update_not_playing(hass: HomeAssistant) -> None:
    """Test update when no playing song."""
    with patch_interface():
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


async def test_update_playing(hass: HomeAssistant) -> None:
    """Test update when song playing."""
    with patch_interface(MOCK_TRACK):
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
