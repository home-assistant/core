"""Test the Frontier Silicon media player entity."""

from unittest.mock import AsyncMock

from afsapi import FSConnectionError, FSNotImplementedError
import pytest

from homeassistant.components.frontier_silicon.const import DOMAIN
from homeassistant.components.frontier_silicon.media_player import AFSAPIDevice
from homeassistant.exceptions import HomeAssistantError


async def test_async_media_previous_track_maps_connection_error() -> None:
    """Test previous track maps connection failures to Home Assistant errors."""
    fs_device = AsyncMock()
    fs_device.rewind.side_effect = FSConnectionError("Connection failed")
    entity = AFSAPIDevice("unique_id", "name", fs_device)

    with pytest.raises(HomeAssistantError) as exc_info:
        await entity.async_media_previous_track()

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "connection_error"
    assert exc_info.value.translation_placeholders == {
        "command": "media_previous_track"
    }


async def test_async_media_previous_track_maps_other_api_errors() -> None:
    """Test previous track maps non-range API errors to Home Assistant errors."""
    fs_device = AsyncMock()
    fs_device.rewind.side_effect = FSNotImplementedError("Command is not implemented")
    entity = AFSAPIDevice("unique_id", "name", fs_device)

    with pytest.raises(HomeAssistantError) as exc_info:
        await entity.async_media_previous_track()

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "api_error"
    assert exc_info.value.translation_placeholders["command"] == "media_previous_track"
    assert (
        "Command is not implemented"
        in exc_info.value.translation_placeholders["message"]
    )
