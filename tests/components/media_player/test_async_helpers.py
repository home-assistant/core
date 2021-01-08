"""The tests for the Async Media player helper functions."""
import asyncio
import unittest

import homeassistant.components.media_player as mp
from homeassistant.const import (
    STATE_IDLE,
    STATE_OFF,
    STATE_ON,
    STATE_PAUSED,
    STATE_PLAYING,
)

from tests.common import get_test_home_assistant


class AsyncMediaPlayer(mp.MediaPlayerEntity):
    """Async media player test class."""

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
            | mp.const.SUPPORT_PLAY
            | mp.const.SUPPORT_PAUSE
            | mp.const.SUPPORT_TURN_OFF
            | mp.const.SUPPORT_TURN_ON
        )

    async def async_set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        self._volume = volume

    async def async_media_play(self):
        """Send play command."""
        self._state = STATE_PLAYING

    async def async_media_pause(self):
        """Send pause command."""
        self._state = STATE_PAUSED

    async def async_turn_on(self):
        """Turn the media player on."""
        self._state = STATE_ON

    async def async_turn_off(self):
        """Turn the media player off."""
        self._state = STATE_OFF


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


class TestAsyncMediaPlayer(unittest.TestCase):
    """Test the media_player module."""

    def setUp(self):  # pylint: disable=invalid-name
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.player = AsyncMediaPlayer(self.hass)
        self.addCleanup(self.tear_down_cleanup)

    def tear_down_cleanup(self):
        """Shut down test instance."""
        self.hass.stop()

    def test_volume_up(self):
        """Test the volume_up helper function."""
        assert self.player.volume_level == 0
        asyncio.run_coroutine_threadsafe(
            self.player.async_set_volume_level(0.5), self.hass.loop
        ).result()
        assert self.player.volume_level == 0.5
        asyncio.run_coroutine_threadsafe(
            self.player.async_volume_up(), self.hass.loop
        ).result()
        assert self.player.volume_level == 0.6

    def test_volume_down(self):
        """Test the volume_down helper function."""
        assert self.player.volume_level == 0
        asyncio.run_coroutine_threadsafe(
            self.player.async_set_volume_level(0.5), self.hass.loop
        ).result()
        assert self.player.volume_level == 0.5
        asyncio.run_coroutine_threadsafe(
            self.player.async_volume_down(), self.hass.loop
        ).result()
        assert self.player.volume_level == 0.4

    def test_media_play_pause(self):
        """Test the media_play_pause helper function."""
        assert self.player.state == STATE_OFF
        asyncio.run_coroutine_threadsafe(
            self.player.async_media_play_pause(), self.hass.loop
        ).result()
        assert self.player.state == STATE_PLAYING
        asyncio.run_coroutine_threadsafe(
            self.player.async_media_play_pause(), self.hass.loop
        ).result()
        assert self.player.state == STATE_PAUSED

    def test_toggle(self):
        """Test the toggle helper function."""
        assert self.player.state == STATE_OFF
        asyncio.run_coroutine_threadsafe(
            self.player.async_toggle(), self.hass.loop
        ).result()
        assert self.player.state == STATE_ON
        asyncio.run_coroutine_threadsafe(
            self.player.async_toggle(), self.hass.loop
        ).result()
        assert self.player.state == STATE_OFF


class TestSyncMediaPlayer(unittest.TestCase):
    """Test the media_player module."""

    def setUp(self):  # pylint: disable=invalid-name
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.player = SyncMediaPlayer(self.hass)
        self.addCleanup(self.tear_down_cleanup)

    def tear_down_cleanup(self):
        """Shut down test instance."""
        self.hass.stop()

    def test_volume_up(self):
        """Test the volume_up helper function."""
        assert self.player.volume_level == 0
        self.player.set_volume_level(0.5)
        assert self.player.volume_level == 0.5
        asyncio.run_coroutine_threadsafe(
            self.player.async_volume_up(), self.hass.loop
        ).result()
        assert self.player.volume_level == 0.7

    def test_volume_down(self):
        """Test the volume_down helper function."""
        assert self.player.volume_level == 0
        self.player.set_volume_level(0.5)
        assert self.player.volume_level == 0.5
        asyncio.run_coroutine_threadsafe(
            self.player.async_volume_down(), self.hass.loop
        ).result()
        assert self.player.volume_level == 0.3

    def test_media_play_pause(self):
        """Test the media_play_pause helper function."""
        assert self.player.state == STATE_OFF
        asyncio.run_coroutine_threadsafe(
            self.player.async_media_play_pause(), self.hass.loop
        ).result()
        assert self.player.state == STATE_PLAYING
        asyncio.run_coroutine_threadsafe(
            self.player.async_media_play_pause(), self.hass.loop
        ).result()
        assert self.player.state == STATE_PAUSED

    def test_toggle(self):
        """Test the toggle helper function."""
        assert self.player.state == STATE_OFF
        asyncio.run_coroutine_threadsafe(
            self.player.async_toggle(), self.hass.loop
        ).result()
        assert self.player.state == STATE_ON
        asyncio.run_coroutine_threadsafe(
            self.player.async_toggle(), self.hass.loop
        ).result()
        assert self.player.state == STATE_OFF
