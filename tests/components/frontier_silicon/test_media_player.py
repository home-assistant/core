"""Test the Frontier Silicon media player entity."""

from unittest.mock import AsyncMock

from afsapi import FSConnectionError, FSNotImplementedError
import pytest

from homeassistant.components.frontier_silicon.media_player import AFSAPIDevice
from homeassistant.exceptions import HomeAssistantError


@pytest.mark.parametrize(
    ("error", "translation_key", "message"),
    [
        (FSConnectionError("Connection failed"), "connection_error", None),
        (
            FSNotImplementedError("Command is not implemented"),
            "api_error",
            "Command is not implemented",
        ),
    ],
)
async def test_async_media_previous_track_maps_errors(
    error: Exception, translation_key: str, message: str | None
) -> None:
    """Test previous track maps API failures to Home Assistant errors."""
    fs_device = AsyncMock()
    fs_device.rewind.side_effect = error
    entity = AFSAPIDevice("unique_id", "name", fs_device)

    with pytest.raises(HomeAssistantError) as exc_info:
        await entity.async_media_previous_track()

    assert exc_info.value.translation_key == translation_key
    assert exc_info.value.translation_placeholders["command"] == "media_previous_track"

    assert (
        message is None or message in exc_info.value.translation_placeholders["message"]
    )
