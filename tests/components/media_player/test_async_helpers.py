"""The tests for the Async Media player helper functions."""
import unittest
import asyncio

import homeassistant.components.media_player as mp
from homeassistant.const import (
    STATE_PLAYING, STATE_PAUSED, STATE_ON, STATE_OFF, STATE_IDLE)
from homeassistant.util.async_ import run_coroutine_threadsafe

from tests.common import get_test_home_assistant


class AsyncMediaPlayer(mp.MediaPlayerDevice):
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

    @asyncio.coroutine
    def async_set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        self._volume = volume

    @asyncio.coroutine
    def async_media_play(self):
        """Send play command."""
        self._state = STATE_PLAYING

    @asyncio.coroutine
    def async_media_pause(self):
        """Send pause command."""
        self._state = STATE_PAUSED

    @asyncio.coroutine
    def async_turn_on(self):
        """Turn the media player on."""
        self._state = STATE_ON

    @asyncio.coroutine
    def async_turn_off(self):
        """Turn the media player off."""
        self._state = STATE_OFF


class SyncMediaPlayer(mp.MediaPlayerDevice):
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

    def set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        self._volume = volume

    def volume_up(self):
        """Turn volume up for media player."""
        if self.volume_level < 1:
            self.set_volume_level(min(1, self.volume_level + .2))

    def volume_down(self):
        """Turn volume down for media player."""
        if self.volume_level > 0:
            self.set_volume_level(max(0, self.volume_level - .2))

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

    @asyncio.coroutine
    def async_media_play_pause(self):
        """Create a coroutine to wrap the future returned by ABC.

        This allows the run_coroutine_threadsafe helper to be used.
        """
        yield from super().async_media_play_pause()

    @asyncio.coroutine
    def async_toggle(self):
        """Create a coroutine to wrap the future returned by ABC.

        This allows the run_coroutine_threadsafe helper to be used.
        """
        yield from super().async_toggle()


class TestAsyncMediaPlayer(unittest.TestCase):
    """Test the media_player module."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.player = AsyncMediaPlayer(self.hass)

    def tearDown(self):
        """Shut down test instance."""
        self.hass.stop()

    def test_volume_up(self):
        """Test the volume_up helper function."""
        self.assertEqual(self.player.volume_level, 0)
        run_coroutine_threadsafe(
            self.player.async_set_volume_level(0.5), self.hass.loop).result()
        self.assertEqual(self.player.volume_level, 0.5)
        run_coroutine_threadsafe(
            self.player.async_volume_up(), self.hass.loop).result()
        self.assertEqual(self.player.volume_level, 0.6)

    def test_volume_down(self):
        """Test the volume_down helper function."""
        self.assertEqual(self.player.volume_level, 0)
        run_coroutine_threadsafe(
            self.player.async_set_volume_level(0.5), self.hass.loop).result()
        self.assertEqual(self.player.volume_level, 0.5)
        run_coroutine_threadsafe(
            self.player.async_volume_down(), self.hass.loop).result()
        self.assertEqual(self.player.volume_level, 0.4)

    def test_media_play_pause(self):
        """Test the media_play_pause helper function."""
        self.assertEqual(self.player.state, STATE_OFF)
        run_coroutine_threadsafe(
            self.player.async_media_play_pause(), self.hass.loop).result()
        self.assertEqual(self.player.state, STATE_PLAYING)
        run_coroutine_threadsafe(
            self.player.async_media_play_pause(), self.hass.loop).result()
        self.assertEqual(self.player.state, STATE_PAUSED)

    def test_toggle(self):
        """Test the toggle helper function."""
        self.assertEqual(self.player.state, STATE_OFF)
        run_coroutine_threadsafe(
            self.player.async_toggle(), self.hass.loop).result()
        self.assertEqual(self.player.state, STATE_ON)
        run_coroutine_threadsafe(
            self.player.async_toggle(), self.hass.loop).result()
        self.assertEqual(self.player.state, STATE_OFF)


class TestSyncMediaPlayer(unittest.TestCase):
    """Test the media_player module."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.player = SyncMediaPlayer(self.hass)

    def tearDown(self):
        """Shut down test instance."""
        self.hass.stop()

    def test_volume_up(self):
        """Test the volume_up helper function."""
        self.assertEqual(self.player.volume_level, 0)
        self.player.set_volume_level(0.5)
        self.assertEqual(self.player.volume_level, 0.5)
        run_coroutine_threadsafe(
            self.player.async_volume_up(), self.hass.loop).result()
        self.assertEqual(self.player.volume_level, 0.7)

    def test_volume_down(self):
        """Test the volume_down helper function."""
        self.assertEqual(self.player.volume_level, 0)
        self.player.set_volume_level(0.5)
        self.assertEqual(self.player.volume_level, 0.5)
        run_coroutine_threadsafe(
            self.player.async_volume_down(), self.hass.loop).result()
        self.assertEqual(self.player.volume_level, 0.3)

    def test_media_play_pause(self):
        """Test the media_play_pause helper function."""
        self.assertEqual(self.player.state, STATE_OFF)
        run_coroutine_threadsafe(
            self.player.async_media_play_pause(), self.hass.loop).result()
        self.assertEqual(self.player.state, STATE_PLAYING)
        run_coroutine_threadsafe(
            self.player.async_media_play_pause(), self.hass.loop).result()
        self.assertEqual(self.player.state, STATE_PAUSED)

    def test_toggle(self):
        """Test the toggle helper function."""
        self.assertEqual(self.player.state, STATE_OFF)
        run_coroutine_threadsafe(
            self.player.async_toggle(), self.hass.loop).result()
        self.assertEqual(self.player.state, STATE_ON)
        run_coroutine_threadsafe(
            self.player.async_toggle(), self.hass.loop).result()
        self.assertEqual(self.player.state, STATE_OFF)
