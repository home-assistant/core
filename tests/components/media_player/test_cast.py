"""
tests.component.media_player.test_cast
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests cast media_player component.
"""
# pylint: disable=too-many-public-methods,protected-access
import unittest
from unittest.mock import patch

from homeassistant.components.media_player import cast


class TestCastMediaPlayer(unittest.TestCase):
    """ Test the media_player module. """

    @patch('homeassistant.components.media_player.cast.CastDevice')
    def test_filter_duplicates(self, mock_device):
        cast.setup_platform(None, {
            'host': 'some_host'
        }, lambda _: _)

        assert mock_device.called

        mock_device.reset_mock()
        assert not mock_device.called

        cast.setup_platform(None, {}, lambda _: _, ('some_host',
                                                    cast.DEFAULT_PORT))
        assert not mock_device.called
