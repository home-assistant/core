"""The tests for the LG webOS media player platform."""
import unittest
from unittest import mock

from homeassistant.components.media_player import webostv


class FakeLgWebOSDevice(webostv.LgWebOSDevice):
    """A fake device without the client setup required for the real one."""

    def __init__(self, *args, **kwargs):
        """Initialise parameters needed for tests with fake values."""
        self._source_list = {}
        self._client = mock.MagicMock()
        self._name = 'fake_device'
        self._current_source = None


class TestLgWebOSDevice(unittest.TestCase):
    """Test the LgWebOSDevice class."""

    def setUp(self):
        """Configure a fake device for each test."""
        self.device = FakeLgWebOSDevice()

    def test_select_source_with_empty_source_list(self):
        """Ensure we don't call client methods when we don't have sources."""
        self.device.select_source('nonexistent')
        assert 0 == self.device._client.launch_app.call_count
        assert 0 == self.device._client.set_input.call_count

    def test_select_source_with_titled_entry(self):
        """Test that a titled source is treated as an app."""
        self.device._source_list = {
            'existent': {
                'id': 'existent_id',
                'title': 'existent_title',
            },
        }

        self.device.select_source('existent')

        assert 'existent_title' == self.device._current_source
        assert [mock.call('existent_id')] == (
            self.device._client.launch_app.call_args_list)

    def test_select_source_with_labelled_entry(self):
        """Test that a labelled source is treated as an input source."""
        self.device._source_list = {
            'existent': {
                'id': 'existent_id',
                'label': 'existent_label',
            },
        }

        self.device.select_source('existent')

        assert 'existent_label' == self.device._current_source
        assert [mock.call('existent_id')] == (
            self.device._client.set_input.call_args_list)
