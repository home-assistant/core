"""Test the UniFi Protect camera platform."""
from __future__ import annotations

from typing import cast
from unittest.mock import AsyncMock

from pyunifiprotect.data import Camera as ProtectCamera

from homeassistant.components.camera import Camera, async_get_image
from homeassistant.components.unifiprotect.const import (
    ATTR_BITRATE,
    ATTR_CHANNEL_ID,
    ATTR_FPS,
    ATTR_HEIGHT,
    ATTR_WIDTH,
    DEFAULT_ATTRIBUTION,
)
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import MockEntityFixture


async def validate_camera_entity(
    hass: HomeAssistant,
    camera: ProtectCamera,
    channel_id: int,
    secure: bool,
    rtsp_enabled: bool,
    enabled: bool,
):
    """Validate a camera entity."""

    channel = camera.channels[channel_id]

    entity_name = f"{camera.name} {channel.name}"
    unique_id = f"{camera.id}_{channel.id}"
    if not secure:
        entity_name += " Insecure"
        unique_id += "_insecure"
    entity_id = f"camera.{entity_name.replace(' ', '_').lower()}"

    entity_registry = er.async_get(hass)
    entity = entity_registry.async_get(entity_id)
    assert entity
    assert entity.disabled is (not enabled)
    assert entity.unique_id == unique_id

    camera_platform = hass.data.get("camera")
    assert camera_platform

    if not enabled:
        return

    ha_camera = cast(Camera, camera_platform.get_entity(entity_id))
    assert ha_camera
    if rtsp_enabled:
        if secure:
            assert await ha_camera.stream_source() == channel.rtsps_url
        else:
            assert await ha_camera.stream_source() == channel.rtsp_url
    else:
        assert await ha_camera.stream_source() is None

    entity_state = hass.states.get(entity_id)
    assert entity_state
    assert entity_state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION
    assert entity_state.attributes[ATTR_WIDTH] == channel.width
    assert entity_state.attributes[ATTR_HEIGHT] == channel.height
    assert entity_state.attributes[ATTR_FPS] == channel.fps
    assert entity_state.attributes[ATTR_BITRATE] == channel.bitrate
    assert entity_state.attributes[ATTR_CHANNEL_ID] == channel.id


async def test_basic_setup(
    hass: HomeAssistant, mock_entry: MockEntityFixture, mock_camera: ProtectCamera
):
    """Test working setup of unifiprotect entry."""

    camera_high_only = mock_camera.copy(deep=True)
    camera_high_only._api = mock_entry.api
    camera_high_only.channels[0]._api = mock_entry.api
    camera_high_only.channels[1]._api = mock_entry.api
    camera_high_only.channels[2]._api = mock_entry.api
    camera_high_only.name = "Test Camera 1"
    camera_high_only.id = "test_high"
    camera_high_only.channels[0].is_rtsp_enabled = True
    camera_high_only.channels[0].name = "High"
    camera_high_only.channels[0].rtsp_alias = "test_high_alias"
    camera_high_only.channels[1].is_rtsp_enabled = False
    camera_high_only.channels[2].is_rtsp_enabled = False

    camera_all_channels = mock_camera.copy(deep=True)
    camera_all_channels._api = mock_entry.api
    camera_all_channels.channels[0]._api = mock_entry.api
    camera_all_channels.channels[1]._api = mock_entry.api
    camera_all_channels.channels[2]._api = mock_entry.api
    camera_all_channels.name = "Test Camera 2"
    camera_all_channels.id = "test_all"
    camera_all_channels.channels[0].is_rtsp_enabled = True
    camera_all_channels.channels[0].name = "High"
    camera_all_channels.channels[0].rtsp_alias = "test_high_alias"
    camera_all_channels.channels[1].is_rtsp_enabled = True
    camera_all_channels.channels[1].name = "Medium"
    camera_all_channels.channels[1].rtsp_alias = "test_medium_alias"
    camera_all_channels.channels[2].is_rtsp_enabled = True
    camera_all_channels.channels[2].name = "Low"
    camera_all_channels.channels[2].rtsp_alias = "test_low_alias"

    camera_no_channels = mock_camera.copy(deep=True)
    camera_no_channels._api = mock_entry.api
    camera_no_channels.channels[0]._api = mock_entry.api
    camera_no_channels.channels[1]._api = mock_entry.api
    camera_no_channels.channels[2]._api = mock_entry.api
    camera_no_channels.name = "Test Camera 3"
    camera_no_channels.id = "test_none"
    camera_no_channels.channels[0].is_rtsp_enabled = False
    camera_no_channels.channels[0].name = "High"
    camera_no_channels.channels[1].is_rtsp_enabled = False
    camera_no_channels.channels[2].is_rtsp_enabled = False

    mock_entry.api.bootstrap.cameras = {
        camera_high_only.id: camera_high_only,
        camera_all_channels.id: camera_all_channels,
        camera_no_channels.id: camera_no_channels,
    }

    await hass.config_entries.async_setup(mock_entry.entry.entry_id)
    await hass.async_block_till_done()

    await validate_camera_entity(
        hass, camera_high_only, 0, secure=True, rtsp_enabled=True, enabled=True
    )
    await validate_camera_entity(
        hass, camera_high_only, 0, secure=False, rtsp_enabled=True, enabled=False
    )

    await validate_camera_entity(
        hass, camera_all_channels, 0, secure=True, rtsp_enabled=True, enabled=True
    )
    await validate_camera_entity(
        hass, camera_all_channels, 0, secure=False, rtsp_enabled=True, enabled=False
    )
    await validate_camera_entity(
        hass, camera_all_channels, 1, secure=True, rtsp_enabled=True, enabled=False
    )
    await validate_camera_entity(
        hass, camera_all_channels, 1, secure=False, rtsp_enabled=True, enabled=False
    )
    await validate_camera_entity(
        hass, camera_all_channels, 2, secure=True, rtsp_enabled=True, enabled=False
    )
    await validate_camera_entity(
        hass, camera_all_channels, 2, secure=False, rtsp_enabled=True, enabled=False
    )

    await validate_camera_entity(
        hass, camera_no_channels, 0, secure=True, rtsp_enabled=False, enabled=True
    )


async def test_missing_channels(
    hass: HomeAssistant, mock_entry: MockEntityFixture, mock_camera: ProtectCamera
):
    """Test setting up camera with no camera channels."""

    camera = mock_camera.copy(deep=True)
    camera.channels = []

    mock_entry.api.bootstrap.cameras = {camera.id: camera}

    await hass.config_entries.async_setup(mock_entry.entry.entry_id)
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)

    assert len(hass.states.async_all()) == 0
    assert len(entity_registry.entities) == 0


async def test_camera_image(
    hass: HomeAssistant, mock_entry: MockEntityFixture, mock_camera: ProtectCamera
):
    """Test retrieving camera image."""

    camera = mock_camera.copy(deep=True)
    camera._api = mock_entry.api
    camera.channels[0]._api = mock_entry.api
    camera.channels[1]._api = mock_entry.api
    camera.channels[2]._api = mock_entry.api
    camera.name = "Test Camera"
    camera.channels[0].is_rtsp_enabled = True
    camera.channels[0].name = "High"
    camera.channels[1].is_rtsp_enabled = False
    camera.channels[2].is_rtsp_enabled = False

    mock_entry.api.get_camera_snapshot = AsyncMock()
    mock_entry.api.bootstrap.cameras = {camera.id: camera}

    await hass.config_entries.async_setup(mock_entry.entry.entry_id)
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)

    assert len(hass.states.async_all()) == 1
    assert len(entity_registry.entities) == 2

    await async_get_image(hass, "camera.test_camera_high")
    mock_entry.api.get_camera_snapshot.assert_called_once()
