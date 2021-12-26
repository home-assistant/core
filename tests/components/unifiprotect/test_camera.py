"""Test the UniFi Protect camera platform."""
from __future__ import annotations

from copy import copy
from typing import cast
from unittest.mock import AsyncMock, Mock

from pyunifiprotect.data import Camera as ProtectCamera
from pyunifiprotect.exceptions import NvrError

from homeassistant.components.camera import Camera, async_get_image
from homeassistant.components.unifiprotect.const import (
    ATTR_BITRATE,
    ATTR_CHANNEL_ID,
    ATTR_FPS,
    ATTR_HEIGHT,
    ATTR_WIDTH,
    DEFAULT_ATTRIBUTION,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from homeassistant.components.unifiprotect.data import ProtectData
from homeassistant.const import ATTR_ATTRIBUTION, ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from .conftest import MockEntityFixture, time_changed


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

    if not enabled:
        return

    camera_platform = hass.data.get("camera")
    assert camera_platform
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
    hass: HomeAssistant,
    mock_entry: MockEntityFixture,
    simple_camera: tuple[Camera, str],
):
    """Test retrieving camera image."""

    mock_entry.api.get_camera_snapshot = AsyncMock()

    await async_get_image(hass, simple_camera[1])
    mock_entry.api.get_camera_snapshot.assert_called_once()


async def test_camera_generic_update(
    hass: HomeAssistant,
    mock_entry: MockEntityFixture,
    simple_camera: tuple[ProtectCamera, str],
):
    """Tests generic entity update service."""

    assert await async_setup_component(hass, "homeassistant", {})

    data: ProtectData = hass.data[DOMAIN][mock_entry.entry.entry_id]
    assert data
    assert data.last_update_success

    state = hass.states.get(simple_camera[1])
    assert state and state.state == "idle"

    mock_entry.api.update = AsyncMock(return_value=None)
    await hass.services.async_call(
        "homeassistant",
        "update_entity",
        {ATTR_ENTITY_ID: simple_camera[1]},
        blocking=True,
    )

    state = hass.states.get(simple_camera[1])
    assert state and state.state == "idle"


async def test_camera_interval_update(
    hass: HomeAssistant,
    mock_entry: MockEntityFixture,
    simple_camera: tuple[ProtectCamera, str],
):
    """Interval updates updates camera entity."""

    data: ProtectData = hass.data[DOMAIN][mock_entry.entry.entry_id]
    assert data
    assert data.last_update_success

    state = hass.states.get(simple_camera[1])
    assert state and state.state == "idle"

    new_bootstrap = copy(mock_entry.api.bootstrap)
    new_camera = simple_camera[0].copy()
    new_camera.is_recording = True

    new_bootstrap.cameras = {new_camera.id: new_camera}
    mock_entry.api.update = AsyncMock(return_value=new_bootstrap)
    mock_entry.api.bootstrap = new_bootstrap
    await time_changed(hass, DEFAULT_SCAN_INTERVAL)

    state = hass.states.get(simple_camera[1])
    assert state and state.state == "recording"


async def test_camera_bad_interval_update(
    hass: HomeAssistant,
    mock_entry: MockEntityFixture,
    simple_camera: tuple[Camera, str],
):
    """Interval updates marks camera unavailable."""

    data: ProtectData = hass.data[DOMAIN][mock_entry.entry.entry_id]
    assert data
    assert data.last_update_success

    state = hass.states.get(simple_camera[1])
    assert state and state.state == "idle"

    # update fails
    mock_entry.api.update = AsyncMock(side_effect=NvrError)
    await time_changed(hass, DEFAULT_SCAN_INTERVAL)

    assert not data.last_update_success
    state = hass.states.get(simple_camera[1])
    assert state and state.state == "unavailable"

    # next update succeeds
    mock_entry.api.update = AsyncMock(return_value=mock_entry.api.bootstrap)
    await time_changed(hass, DEFAULT_SCAN_INTERVAL)

    assert data.last_update_success
    state = hass.states.get(simple_camera[1])
    assert state and state.state == "idle"


async def test_camera_ws_update(
    hass: HomeAssistant,
    mock_entry: MockEntityFixture,
    simple_camera: tuple[ProtectCamera, str],
):
    """WS update updates camera entity."""

    data: ProtectData = hass.data[DOMAIN][mock_entry.entry.entry_id]
    assert data
    assert data.last_update_success

    state = hass.states.get(simple_camera[1])
    assert state and state.state == "idle"

    new_bootstrap = copy(mock_entry.api.bootstrap)
    new_camera = simple_camera[0].copy()
    new_camera.is_recording = True

    mock_msg = Mock()
    mock_msg.new_obj = new_camera

    new_bootstrap.cameras = {new_camera.id: new_camera}
    mock_entry.api.bootstrap = new_bootstrap
    mock_entry.api.ws_subscription(mock_msg)
    await hass.async_block_till_done()

    state = hass.states.get(simple_camera[1])
    assert state and state.state == "recording"


async def test_camera_ws_update_offline(
    hass: HomeAssistant,
    mock_entry: MockEntityFixture,
    simple_camera: tuple[ProtectCamera, str],
):
    """WS updates marks camera unavailable."""

    data: ProtectData = hass.data[DOMAIN][mock_entry.entry.entry_id]
    assert data
    assert data.last_update_success

    state = hass.states.get(simple_camera[1])
    assert state and state.state == "idle"

    # camera goes offline
    new_bootstrap = copy(mock_entry.api.bootstrap)
    new_camera = simple_camera[0].copy()
    new_camera.is_connected = False

    mock_msg = Mock()
    mock_msg.new_obj = new_camera

    new_bootstrap.cameras = {new_camera.id: new_camera}
    mock_entry.api.bootstrap = new_bootstrap
    mock_entry.api.ws_subscription(mock_msg)
    await hass.async_block_till_done()

    state = hass.states.get(simple_camera[1])
    assert state and state.state == "unavailable"

    # camera comes back online
    new_camera.is_connected = True

    mock_msg = Mock()
    mock_msg.new_obj = new_camera

    new_bootstrap.cameras = {new_camera.id: new_camera}
    mock_entry.api.bootstrap = new_bootstrap
    mock_entry.api.ws_subscription(mock_msg)
    await hass.async_block_till_done()

    state = hass.states.get(simple_camera[1])
    assert state and state.state == "idle"
