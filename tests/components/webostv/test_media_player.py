"""The tests for the LG webOS media player platform."""
import unittest
from unittest import mock

from homeassistant.components.webostv import media_player as webostv


class TestLgWebOSMediaPlayerEntity(unittest.IsolatedAsyncioTestCase):
    """Test the LgWebOSMediaPlayerEntity class."""

    def setUp(self):
        """Configure a fake device for each test."""
        self.device = webostv.LgWebOSMediaPlayerEntity(mock.AsyncMock(), "fake_device")

    async def test_select_source_with_empty_source_list(self):
        """Ensure we don't call client methods when we don't have sources."""
        await self.device.async_select_source("nonexistent")
        assert 0 == self.device._client.launch_app.call_count
        assert 0 == self.device._client.set_input.call_count

    async def test_select_source_with_titled_entry(self):
        """Test that a titled source is treated as an app."""
        self.device._source_list = {
            "existent": {"id": "existent_id", "title": "existent_title"}
        }

        await self.device.async_select_source("existent")

        assert "existent_title" == self.device._current_source
        assert [mock.call("existent_id")] == (
            self.device._client.launch_app.call_args_list
        )

    async def test_select_source_with_labelled_entry(self):
        """Test that a labelled source is treated as an input source."""
        self.device._source_list = {
            "existent": {"id": "existent_id", "label": "existent_label"}
        }

        await self.device.async_select_source("existent")

        assert "existent_label" == self.device._current_source
        assert [mock.call("existent_id")] == (
            self.device._client.set_input.call_args_list
        )
