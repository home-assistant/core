"""The tests for the Async Media player helper functions."""
import unittest
import asyncio

import homeassistant.components.media_player as mp
from homeassistant.util.async import run_coroutine_threadsafe

from tests.common import get_test_home_assistant


class AsyncMediaPlayer(mp.MediaPlayerDevice):
    """Async media player test class."""

    def __init__(self, hass):
        """Initialize the test media player."""
        self.hass = hass
        self._volume = 0

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        return self._volume

    @asyncio.coroutine
    def async_set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        self._volume = volume


class SyncMediaPlayer(mp.MediaPlayerDevice):
    """Sync media player test class."""

    def __init__(self, hass):
        """Initialize the test media player."""
        self.hass = hass
        self._volume = 0

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
