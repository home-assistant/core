"""Test the Frontier Silicon media player entity."""

from unittest.mock import AsyncMock

from afsapi.exceptions import (
    FSConnectionError,
    FSNodeBlockedError,
    FSNotImplementedError,
    OutOfRangeError,
)
import pytest

from homeassistant.components.frontier_silicon.media_player import AFSAPIDevice
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError


async def test_async_media_previous_track_maps_out_of_range_error() -> None:
    """Test previous track maps API range errors to service validation errors."""
    fs_device = AsyncMock()
    fs_device.rewind.side_effect = OutOfRangeError(
        "Command failed. Value is not in range for this command."
    )
    entity = AFSAPIDevice("unique_id", "name", fs_device)

    with pytest.raises(
        ServiceValidationError,
        match="Command failed. Value is not in range for this command.",
    ):
        await entity.async_media_previous_track()


async def test_async_media_previous_track_maps_node_blocked_error() -> None:
    """Test previous track maps API node blocked errors to service validation errors."""
    fs_device = AsyncMock()
    fs_device.rewind.side_effect = FSNodeBlockedError(
        "Command failed. Node is blocked."
    )
    entity = AFSAPIDevice("unique_id", "name", fs_device)

    with pytest.raises(
        ServiceValidationError,
        match="Command failed. Node is blocked.",
    ):
        await entity.async_media_previous_track()


async def test_async_media_previous_track_maps_connection_error() -> None:
    """Test previous track maps connection failures to Home Assistant errors."""
    fs_device = AsyncMock()
    fs_device.rewind.side_effect = FSConnectionError("Connection failed")
    entity = AFSAPIDevice("unique_id", "name", fs_device)

    with pytest.raises(
        HomeAssistantError,
        match="Failed to execute media_previous_track: could not connect to device",
    ):
        await entity.async_media_previous_track()


async def test_async_media_previous_track_maps_other_api_errors() -> None:
    """Test previous track maps non-range API errors to Home Assistant errors."""
    fs_device = AsyncMock()
    fs_device.rewind.side_effect = FSNotImplementedError("Command is not implemented")
    entity = AFSAPIDevice("unique_id", "name", fs_device)

    with pytest.raises(
        HomeAssistantError,
        match="Failed to execute media_previous_track: Command is not implemented",
    ):
        await entity.async_media_previous_track()
