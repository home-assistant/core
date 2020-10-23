"""The tests for the Sync Media player helper functions."""

import pytest

import homeassistant.components.media_player as mp
from homeassistant.const import (
    STATE_IDLE,
    STATE_OFF,
    STATE_ON,
    STATE_PAUSED,
    STATE_PLAYING,
)


class SyncMediaPlayer(mp.MediaPlayerEntity):
    """Sync media player test class."""

    def __init__(self, hass):
        """Initialize the test media player."""
        self.hass = hass
        self._volume = 0
        self._state = STATE_OFF

    @property
    def state(self):
        """State of the player."""
        return self._state

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        return self._volume

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return (
            mp.const.SUPPORT_VOLUME_SET
            | mp.const.SUPPORT_VOLUME_STEP
            | mp.const.SUPPORT_PLAY
            | mp.const.SUPPORT_PAUSE
            | mp.const.SUPPORT_TURN_OFF
            | mp.const.SUPPORT_TURN_ON
        )

    def set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        self._volume = volume

    def volume_up(self):
        """Turn volume up for media player."""
        if self.volume_level < 1:
            self.set_volume_level(min(1, self.volume_level + 0.2))

    def volume_down(self):
        """Turn volume down for media player."""
        if self.volume_level > 0:
            self.set_volume_level(max(0, self.volume_level - 0.2))

    def media_play_pause(self):
        """Play or pause the media player."""
        if self._state == STATE_PLAYING:
            self._state = STATE_PAUSED
        else:
            self._state = STATE_PLAYING

    def toggle(self):
        """Toggle the power on the media player."""
        if self._state in [STATE_OFF, STATE_IDLE]:
            self._state = STATE_ON
        else:
            self._state = STATE_OFF

    async def async_media_play_pause(self):
        """Create a coroutine to wrap the future returned by ABC.

        This allows the run_coroutine_threadsafe helper to be used.
        """
        await super().async_media_play_pause()

    async def async_toggle(self):
        """Create a coroutine to wrap the future returned by ABC.

        This allows the run_coroutine_threadsafe helper to be used.
        """
        await super().async_toggle()


@pytest.fixture
def player(hass):
    """Set up sync player to be run when tests are started."""
    return SyncMediaPlayer(hass)


async def test_volume_up(hass, player):
    """Test the volume_up helper function."""
    assert player.volume_level == 0

    player.set_volume_level(0.5)
    assert player.volume_level == 0.5

    await player.async_volume_up()
    assert player.volume_level == 0.7


async def test_volume_down(hass, player):
    """Test the volume_down helper function."""
    assert player.volume_level == 0

    player.set_volume_level(0.5)
    assert player.volume_level == 0.5

    await player.async_volume_down()
    assert player.volume_level == 0.3


async def test_media_play_pause(hass, player):
    """Test the media_play_pause helper function."""
    assert player.state == STATE_OFF

    await player.async_media_play_pause()
    assert player.state == STATE_PLAYING
    await player.async_media_play_pause()
    assert player.state == STATE_PAUSED


async def test_toggle(hass, player):
    """Test the toggle helper function."""
    assert player.state == STATE_OFF

    await player.async_toggle()
    assert player.state == STATE_ON

    await player.async_toggle()
    assert player.state == STATE_OFF
