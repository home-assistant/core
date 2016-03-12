"""The tests for the Cast Media player platform."""
# pylint: disable=too-many-public-methods,protected-access
import unittest
from unittest.mock import patch

from homeassistant.components.media_player import cast


class TestCastMediaPlayer(unittest.TestCase):
    """Test the media_player module."""

    @patch('homeassistant.components.media_player.cast.CastDevice')
    def test_filter_duplicates(self, mock_device):
        """Test filtering of duplicates."""
        cast.setup_platform(None, {
            'host': 'some_host'
        }, lambda _: _)

        assert mock_device.called

        mock_device.reset_mock()
        assert not mock_device.called

        cast.setup_platform(None, {}, lambda _: _, ('some_host',
                                                    cast.DEFAULT_PORT))
        assert not mock_device.called
