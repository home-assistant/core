"""The tests for the LG webOS media player platform."""
from unittest import mock

from homeassistant.components.webostv import media_player as webostv


async def test_select_source_with_empty_source_list():
    """Ensure we don't call client methods when we don't have sources."""
    device = webostv.LgWebOSMediaPlayerEntity(mock.AsyncMock(), "fake_device")
    await device.async_select_source("nonexistent")
    assert 0 == device._client.launch_app.call_count
    assert 0 == device._client.set_input.call_count


async def test_select_source_with_titled_entry():
    """Test that a titled source is treated as an app."""
    device = webostv.LgWebOSMediaPlayerEntity(mock.AsyncMock(), "fake_device")
    device._source_list = {"existent": {"id": "existent_id", "title": "existent_title"}}

    await device.async_select_source("existent")

    assert "existent_title" == device._current_source
    assert [mock.call("existent_id")] == (device._client.launch_app.call_args_list)


async def test_select_source_with_labelled_entry():
    """Test that a labelled source is treated as an input source."""
    device = webostv.LgWebOSMediaPlayerEntity(mock.AsyncMock(), "fake_device")
    device._source_list = {"existent": {"id": "existent_id", "label": "existent_label"}}

    await device.async_select_source("existent")

    assert "existent_label" == device._current_source
    assert [mock.call("existent_id")] == (device._client.set_input.call_args_list)
