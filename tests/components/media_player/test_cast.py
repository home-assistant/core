"""The tests for the Cast Media player platform."""
# pylint: disable=protected-access
import unittest
from unittest.mock import patch, MagicMock

import pytest

from homeassistant.components.media_player import cast


@pytest.fixture(autouse=True)
def cast_mock():
    """Mock pychromecast."""
    with patch.dict('sys.modules', {
        'pychromecast': MagicMock(),
    }):
        yield


class FakeChromeCast(object):
    """A fake Chrome Cast."""

    def __init__(self, host, port):
        """Initialize the fake Chrome Cast."""
        self.host = host
        self.port = port


class TestCastMediaPlayer(unittest.TestCase):
    """Test the media_player module."""

    @patch('homeassistant.components.media_player.cast.CastDevice')
    @patch('pychromecast.get_chromecasts')
    def test_filter_duplicates(self, mock_get_chromecasts, mock_device):
        """Test filtering of duplicates."""
        mock_get_chromecasts.return_value = [
            FakeChromeCast('some_host', cast.DEFAULT_PORT)
        ]

        # Test chromecasts as if they were hardcoded in configuration.yaml
        cast.setup_platform(None, {
            'host': 'some_host'
        }, lambda _: _)

        assert mock_device.called

        mock_device.reset_mock()
        assert not mock_device.called

        # Test chromecasts as if they were automatically discovered
        cast.setup_platform(None, {}, lambda _: _, {
            'host': 'some_host',
            'port': cast.DEFAULT_PORT,
        })
        assert not mock_device.called
