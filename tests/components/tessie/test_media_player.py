"""Test the Tessie media player platform."""
from homeassistant.components.media_player import MediaPlayerState
from homeassistant.core import HomeAssistant

from .common import setup_platform


async def test_sensors(hass: HomeAssistant) -> None:
    """Tests that the sensors are correct."""

    assert len(hass.states.async_all("media_player")) == 0

    await setup_platform(hass)

    assert len(hass.states.async_all("media_player")) == 1

    assert hass.states.get("media_player.test").state == MediaPlayerState.IDLE
