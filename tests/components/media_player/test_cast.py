"""The tests for the Cast Media player platform."""
# pylint: disable=protected-access
import unittest
from unittest.mock import patch, MagicMock

import pytest

from homeassistant.components.media_player import cast
from tests.common import get_test_home_assistant


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

    def setUp(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    @patch('homeassistant.components.media_player.cast.CastDevice')
    @patch('pychromecast.get_chromecasts')
    def test_filter_duplicates(self, mock_get_chromecasts, mock_device):
        """Test filtering of duplicates."""
        mock_get_chromecasts.return_value = [
            FakeChromeCast('some_host', cast.DEFAULT_PORT)
        ]

        # Test chromecasts as if they were hardcoded in configuration.yaml
        cast.setup_platform(self.hass, {
            'host': 'some_host'
        }, lambda _: _)

        assert mock_device.called

        mock_device.reset_mock()
        assert not mock_device.called

        # Test chromecasts as if they were automatically discovered
        cast.setup_platform(self.hass, {}, lambda _: _, {
            'host': 'some_host',
            'port': cast.DEFAULT_PORT,
        })
        assert not mock_device.called

    @patch('homeassistant.components.media_player.cast.CastDevice')
    @patch('pychromecast.get_chromecasts')
    @patch('pychromecast.Chromecast')
    def test_fallback_cast(self, mock_chromecast, mock_get_chromecasts,
                           mock_device):
        """Test falling back to creating Chromecast when not discovered."""
        mock_get_chromecasts.return_value = [
            FakeChromeCast('some_host', cast.DEFAULT_PORT)
        ]

        # Test chromecasts as if they were hardcoded in configuration.yaml
        cast.setup_platform(self.hass, {
            'host': 'some_other_host'
        }, lambda _: _)

        assert mock_chromecast.called
        assert mock_device.called

    @patch('homeassistant.components.media_player.cast.CastDevice')
    @patch('pychromecast.get_chromecasts')
    @patch('pychromecast.Chromecast')
    def test_fallback_cast_group(self, mock_chromecast, mock_get_chromecasts,
                                 mock_device):
        """Test not creating Cast Group when not discovered."""
        mock_get_chromecasts.return_value = [
            FakeChromeCast('some_host', cast.DEFAULT_PORT)
        ]

        # Test chromecasts as if they were automatically discovered
        cast.setup_platform(self.hass, {}, lambda _: _, {
            'host': 'some_other_host',
            'port': 43546,
        })
        assert not mock_chromecast.called
        assert not mock_device.called
