"""Test the UniFi Protect camera platform."""
# pylint: disable=protected-access
from __future__ import annotations

from copy import copy
from unittest.mock import AsyncMock, Mock

import pytest
from pyunifiprotect.data import Camera as ProtectCamera, CameraChannel, StateType
from pyunifiprotect.exceptions import NvrError

from homeassistant.components.camera import (
    SUPPORT_STREAM,
    Camera,
    async_get_image,
    async_get_stream_source,
)
from homeassistant.components.unifiprotect.const import (
    ATTR_BITRATE,
    ATTR_CHANNEL_ID,
    ATTR_FPS,
    ATTR_HEIGHT,
    ATTR_WIDTH,
    DEFAULT_ATTRIBUTION,
    DEFAULT_SCAN_INTERVAL,
)
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from .conftest import (
    MockEntityFixture,
    assert_entity_counts,
    enable_entity,
    regenerate_device_ids,
    time_changed,
)


@pytest.fixture(name="camera")
async def camera_fixture(
    hass: HomeAssistant, mock_entry: MockEntityFixture, mock_camera: Camera
):
    """Fixture for a single camera for testing the camera platform."""

    # disable pydantic validation so mocking can happen
    ProtectCamera.__config__.validate_assignment = False

    camera_obj = mock_camera.copy()
    camera_obj._api = mock_entry.api
    camera_obj.channels[0]._api = mock_entry.api
    camera_obj.channels[1]._api = mock_entry.api
    camera_obj.channels[2]._api = mock_entry.api
    camera_obj.name = "Test Camera"
    camera_obj.channels[0].is_rtsp_enabled = True
    camera_obj.channels[0].name = "High"
    camera_obj.channels[1].is_rtsp_enabled = False
    camera_obj.channels[2].is_rtsp_enabled = False

    mock_entry.api.bootstrap.cameras = {
        camera_obj.id: camera_obj,
    }

    await hass.config_entries.async_setup(mock_entry.entry.entry_id)
    await hass.async_block_till_done()

    assert_entity_counts(hass, Platform.CAMERA, 2, 1)

    yield (camera_obj, "camera.test_camera_high")

    ProtectCamera.__config__.validate_assignment = True


@pytest.fixture(name="camera_package")
async def camera_package_fixture(
    hass: HomeAssistant, mock_entry: MockEntityFixture, mock_camera: Camera
):
    """Fixture for a single camera for testing the camera platform."""

    camera_obj = mock_camera.copy()
    camera_obj._api = mock_entry.api
    camera_obj.channels[0]._api = mock_entry.api
    camera_obj.channels[1]._api = mock_entry.api
    camera_obj.channels[2]._api = mock_entry.api
    camera_obj.name = "Test Camera"
    camera_obj.feature_flags.has_package_camera = True
    camera_obj.channels[0].is_rtsp_enabled = True
    camera_obj.channels[0].name = "High"
    camera_obj.channels[0].rtsp_alias = "test_high_alias"
    camera_obj.channels[1].is_rtsp_enabled = False
    camera_obj.channels[2].is_rtsp_enabled = False
    package_channel = camera_obj.channels[0].copy()
    package_channel.is_rtsp_enabled = False
    package_channel.name = "Package Camera"
    package_channel.id = 3
    package_channel.fps = 2
    package_channel.rtsp_alias = "test_package_alias"
    camera_obj.channels.append(package_channel)

    mock_entry.api.bootstrap.cameras = {
        camera_obj.id: camera_obj,
    }

    await hass.config_entries.async_setup(mock_entry.entry.entry_id)
    await hass.async_block_till_done()

    assert_entity_counts(hass, Platform.CAMERA, 3, 2)

    return (camera_obj, "camera.test_camera_package_camera")


def validate_default_camera_entity(
    hass: HomeAssistant,
    camera_obj: ProtectCamera,
    channel_id: int,
) -> str:
    """Validate a camera entity."""

    channel = camera_obj.channels[channel_id]

    entity_name = f"{camera_obj.name} {channel.name}"
    unique_id = f"{camera_obj.mac}_{channel.id}"
    entity_id = f"camera.{entity_name.replace(' ', '_').lower()}"

    entity_registry = er.async_get(hass)
    entity = entity_registry.async_get(entity_id)
    assert entity
    assert entity.disabled is False
    assert entity.unique_id == unique_id

    return entity_id


def validate_rtsps_camera_entity(
    hass: HomeAssistant,
    camera_obj: ProtectCamera,
    channel_id: int,
) -> str:
    """Validate a disabled RTSPS camera entity."""

    channel = camera_obj.channels[channel_id]

    entity_name = f"{camera_obj.name} {channel.name}"
    unique_id = f"{camera_obj.mac}_{channel.id}"
    entity_id = f"camera.{entity_name.replace(' ', '_').lower()}"

    entity_registry = er.async_get(hass)
    entity = entity_registry.async_get(entity_id)
    assert entity
    assert entity.disabled is True
    assert entity.unique_id == unique_id

    return entity_id


def validate_rtsp_camera_entity(
    hass: HomeAssistant,
    camera_obj: ProtectCamera,
    channel_id: int,
) -> str:
    """Validate a disabled RTSP camera entity."""

    channel = camera_obj.channels[channel_id]

    entity_name = f"{camera_obj.name} {channel.name} Insecure"
    unique_id = f"{camera_obj.mac}_{channel.id}_insecure"
    entity_id = f"camera.{entity_name.replace(' ', '_').lower()}"

    entity_registry = er.async_get(hass)
    entity = entity_registry.async_get(entity_id)
    assert entity
    assert entity.disabled is True
    assert entity.unique_id == unique_id

    return entity_id


def validate_common_camera_state(
    hass: HomeAssistant,
    channel: CameraChannel,
    entity_id: str,
    features: int = SUPPORT_STREAM,
):
    """Validate state that is common to all camera entity, regradless of type."""
    entity_state = hass.states.get(entity_id)
    assert entity_state
    assert entity_state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION
    assert entity_state.attributes[ATTR_SUPPORTED_FEATURES] == features
    assert entity_state.attributes[ATTR_WIDTH] == channel.width
    assert entity_state.attributes[ATTR_HEIGHT] == channel.height
    assert entity_state.attributes[ATTR_FPS] == channel.fps
    assert entity_state.attributes[ATTR_BITRATE] == channel.bitrate
    assert entity_state.attributes[ATTR_CHANNEL_ID] == channel.id


async def validate_rtsps_camera_state(
    hass: HomeAssistant,
    camera_obj: ProtectCamera,
    channel_id: int,
    entity_id: str,
    features: int = SUPPORT_STREAM,
):
    """Validate a camera's state."""
    channel = camera_obj.channels[channel_id]

    assert await async_get_stream_source(hass, entity_id) == channel.rtsps_url
    validate_common_camera_state(hass, channel, entity_id, features)


async def validate_rtsp_camera_state(
    hass: HomeAssistant,
    camera_obj: ProtectCamera,
    channel_id: int,
    entity_id: str,
    features: int = SUPPORT_STREAM,
):
    """Validate a camera's state."""
    channel = camera_obj.channels[channel_id]

    assert await async_get_stream_source(hass, entity_id) == channel.rtsp_url
    validate_common_camera_state(hass, channel, entity_id, features)


async def validate_no_stream_camera_state(
    hass: HomeAssistant,
    camera_obj: ProtectCamera,
    channel_id: int,
    entity_id: str,
    features: int = SUPPORT_STREAM,
):
    """Validate a camera's state."""
    channel = camera_obj.channels[channel_id]

    assert await async_get_stream_source(hass, entity_id) is None
    validate_common_camera_state(hass, channel, entity_id, features)


async def test_basic_setup(
    hass: HomeAssistant, mock_entry: MockEntityFixture, mock_camera: ProtectCamera
):
    """Test working setup of unifiprotect entry."""

    camera_high_only = mock_camera.copy()
    camera_high_only._api = mock_entry.api
    camera_high_only.channels = [c.copy() for c in mock_camera.channels]
    camera_high_only.channels[0]._api = mock_entry.api
    camera_high_only.channels[1]._api = mock_entry.api
    camera_high_only.channels[2]._api = mock_entry.api
    camera_high_only.name = "Test Camera 1"
    camera_high_only.channels[0].is_rtsp_enabled = True
    camera_high_only.channels[0].name = "High"
    camera_high_only.channels[0].rtsp_alias = "test_high_alias"
    camera_high_only.channels[1].is_rtsp_enabled = False
    camera_high_only.channels[2].is_rtsp_enabled = False
    regenerate_device_ids(camera_high_only)

    camera_medium_only = mock_camera.copy()
    camera_medium_only._api = mock_entry.api
    camera_medium_only.channels = [c.copy() for c in mock_camera.channels]
    camera_medium_only.channels[0]._api = mock_entry.api
    camera_medium_only.channels[1]._api = mock_entry.api
    camera_medium_only.channels[2]._api = mock_entry.api
    camera_medium_only.name = "Test Camera 2"
    camera_medium_only.channels[0].is_rtsp_enabled = False
    camera_medium_only.channels[1].is_rtsp_enabled = True
    camera_medium_only.channels[1].name = "Medium"
    camera_medium_only.channels[1].rtsp_alias = "test_medium_alias"
    camera_medium_only.channels[2].is_rtsp_enabled = False
    regenerate_device_ids(camera_medium_only)

    camera_all_channels = mock_camera.copy()
    camera_all_channels._api = mock_entry.api
    camera_all_channels.channels = [c.copy() for c in mock_camera.channels]
    camera_all_channels.channels[0]._api = mock_entry.api
    camera_all_channels.channels[1]._api = mock_entry.api
    camera_all_channels.channels[2]._api = mock_entry.api
    camera_all_channels.name = "Test Camera 3"
    camera_all_channels.channels[0].is_rtsp_enabled = True
    camera_all_channels.channels[0].name = "High"
    camera_all_channels.channels[0].rtsp_alias = "test_high_alias"
    camera_all_channels.channels[1].is_rtsp_enabled = True
    camera_all_channels.channels[1].name = "Medium"
    camera_all_channels.channels[1].rtsp_alias = "test_medium_alias"
    camera_all_channels.channels[2].is_rtsp_enabled = True
    camera_all_channels.channels[2].name = "Low"
    camera_all_channels.channels[2].rtsp_alias = "test_low_alias"
    regenerate_device_ids(camera_all_channels)

    camera_no_channels = mock_camera.copy()
    camera_no_channels._api = mock_entry.api
    camera_no_channels.channels = [c.copy() for c in camera_no_channels.channels]
    camera_no_channels.channels[0]._api = mock_entry.api
    camera_no_channels.channels[1]._api = mock_entry.api
    camera_no_channels.channels[2]._api = mock_entry.api
    camera_no_channels.name = "Test Camera 4"
    camera_no_channels.channels[0].is_rtsp_enabled = False
    camera_no_channels.channels[0].name = "High"
    camera_no_channels.channels[1].is_rtsp_enabled = False
    camera_no_channels.channels[2].is_rtsp_enabled = False
    regenerate_device_ids(camera_no_channels)

    camera_package = mock_camera.copy()
    camera_package._api = mock_entry.api
    camera_package.channels = [c.copy() for c in mock_camera.channels]
    camera_package.channels[0]._api = mock_entry.api
    camera_package.channels[1]._api = mock_entry.api
    camera_package.channels[2]._api = mock_entry.api
    camera_package.name = "Test Camera 5"
    camera_package.channels[0].is_rtsp_enabled = True
    camera_package.channels[0].name = "High"
    camera_package.channels[0].rtsp_alias = "test_high_alias"
    camera_package.channels[1].is_rtsp_enabled = False
    camera_package.channels[2].is_rtsp_enabled = False
    regenerate_device_ids(camera_package)
    package_channel = camera_package.channels[0].copy()
    package_channel.is_rtsp_enabled = False
    package_channel.name = "Package Camera"
    package_channel.id = 3
    package_channel.fps = 2
    package_channel.rtsp_alias = "test_package_alias"
    camera_package.channels.append(package_channel)

    mock_entry.api.bootstrap.cameras = {
        camera_high_only.id: camera_high_only,
        camera_medium_only.id: camera_medium_only,
        camera_all_channels.id: camera_all_channels,
        camera_no_channels.id: camera_no_channels,
        camera_package.id: camera_package,
    }
    await hass.config_entries.async_setup(mock_entry.entry.entry_id)
    await hass.async_block_till_done()

    assert_entity_counts(hass, Platform.CAMERA, 14, 6)

    # test camera 1
    entity_id = validate_default_camera_entity(hass, camera_high_only, 0)
    await validate_rtsps_camera_state(hass, camera_high_only, 0, entity_id)

    entity_id = validate_rtsp_camera_entity(hass, camera_high_only, 0)
    await enable_entity(hass, mock_entry.entry.entry_id, entity_id)
    await validate_rtsp_camera_state(hass, camera_high_only, 0, entity_id)

    # test camera 2
    entity_id = validate_default_camera_entity(hass, camera_medium_only, 1)
    await validate_rtsps_camera_state(hass, camera_medium_only, 1, entity_id)

    entity_id = validate_rtsp_camera_entity(hass, camera_medium_only, 1)
    await enable_entity(hass, mock_entry.entry.entry_id, entity_id)
    await validate_rtsp_camera_state(hass, camera_medium_only, 1, entity_id)

    # test camera 3
    entity_id = validate_default_camera_entity(hass, camera_all_channels, 0)
    await validate_rtsps_camera_state(hass, camera_all_channels, 0, entity_id)

    entity_id = validate_rtsp_camera_entity(hass, camera_all_channels, 0)
    await enable_entity(hass, mock_entry.entry.entry_id, entity_id)
    await validate_rtsp_camera_state(hass, camera_all_channels, 0, entity_id)

    entity_id = validate_rtsps_camera_entity(hass, camera_all_channels, 1)
    await enable_entity(hass, mock_entry.entry.entry_id, entity_id)
    await validate_rtsps_camera_state(hass, camera_all_channels, 1, entity_id)

    entity_id = validate_rtsp_camera_entity(hass, camera_all_channels, 1)
    await enable_entity(hass, mock_entry.entry.entry_id, entity_id)
    await validate_rtsp_camera_state(hass, camera_all_channels, 1, entity_id)

    entity_id = validate_rtsps_camera_entity(hass, camera_all_channels, 2)
    await enable_entity(hass, mock_entry.entry.entry_id, entity_id)
    await validate_rtsps_camera_state(hass, camera_all_channels, 2, entity_id)

    entity_id = validate_rtsp_camera_entity(hass, camera_all_channels, 2)
    await enable_entity(hass, mock_entry.entry.entry_id, entity_id)
    await validate_rtsp_camera_state(hass, camera_all_channels, 2, entity_id)

    # test camera 4
    entity_id = validate_default_camera_entity(hass, camera_no_channels, 0)
    await validate_no_stream_camera_state(
        hass, camera_no_channels, 0, entity_id, features=0
    )

    # test camera 5
    entity_id = validate_default_camera_entity(hass, camera_package, 0)
    await validate_rtsps_camera_state(hass, camera_package, 0, entity_id)

    entity_id = validate_rtsp_camera_entity(hass, camera_package, 0)
    await enable_entity(hass, mock_entry.entry.entry_id, entity_id)
    await validate_rtsp_camera_state(hass, camera_package, 0, entity_id)

    entity_id = validate_default_camera_entity(hass, camera_package, 3)
    await validate_no_stream_camera_state(
        hass, camera_package, 3, entity_id, features=0
    )


async def test_missing_channels(
    hass: HomeAssistant, mock_entry: MockEntityFixture, mock_camera: ProtectCamera
):
    """Test setting up camera with no camera channels."""

    camera = mock_camera.copy()
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
    camera: tuple[Camera, str],
):
    """Test retrieving camera image."""

    mock_entry.api.get_camera_snapshot = AsyncMock()

    await async_get_image(hass, camera[1])
    mock_entry.api.get_camera_snapshot.assert_called_once()


async def test_package_camera_image(
    hass: HomeAssistant,
    mock_entry: MockEntityFixture,
    camera_package: tuple[Camera, str],
):
    """Test retrieving package camera image."""

    mock_entry.api.get_package_camera_snapshot = AsyncMock()

    await async_get_image(hass, camera_package[1])
    mock_entry.api.get_package_camera_snapshot.assert_called_once()


async def test_camera_generic_update(
    hass: HomeAssistant,
    mock_entry: MockEntityFixture,
    camera: tuple[ProtectCamera, str],
):
    """Tests generic entity update service."""

    assert await async_setup_component(hass, "homeassistant", {})

    state = hass.states.get(camera[1])
    assert state and state.state == "idle"

    mock_entry.api.update = AsyncMock(return_value=None)
    await hass.services.async_call(
        "homeassistant",
        "update_entity",
        {ATTR_ENTITY_ID: camera[1]},
        blocking=True,
    )

    state = hass.states.get(camera[1])
    assert state and state.state == "idle"


async def test_camera_interval_update(
    hass: HomeAssistant,
    mock_entry: MockEntityFixture,
    camera: tuple[ProtectCamera, str],
):
    """Interval updates updates camera entity."""

    state = hass.states.get(camera[1])
    assert state and state.state == "idle"

    new_bootstrap = copy(mock_entry.api.bootstrap)
    new_camera = camera[0].copy()
    new_camera.is_recording = True

    new_bootstrap.cameras = {new_camera.id: new_camera}
    mock_entry.api.update = AsyncMock(return_value=new_bootstrap)
    mock_entry.api.bootstrap = new_bootstrap
    await time_changed(hass, DEFAULT_SCAN_INTERVAL)

    state = hass.states.get(camera[1])
    assert state and state.state == "recording"


async def test_camera_bad_interval_update(
    hass: HomeAssistant,
    mock_entry: MockEntityFixture,
    camera: tuple[Camera, str],
):
    """Interval updates marks camera unavailable."""

    state = hass.states.get(camera[1])
    assert state and state.state == "idle"

    # update fails
    mock_entry.api.update = AsyncMock(side_effect=NvrError)
    await time_changed(hass, DEFAULT_SCAN_INTERVAL)

    state = hass.states.get(camera[1])
    assert state and state.state == "unavailable"

    # next update succeeds
    mock_entry.api.update = AsyncMock(return_value=mock_entry.api.bootstrap)
    await time_changed(hass, DEFAULT_SCAN_INTERVAL)

    state = hass.states.get(camera[1])
    assert state and state.state == "idle"


async def test_camera_ws_update(
    hass: HomeAssistant,
    mock_entry: MockEntityFixture,
    camera: tuple[ProtectCamera, str],
):
    """WS update updates camera entity."""

    state = hass.states.get(camera[1])
    assert state and state.state == "idle"

    new_bootstrap = copy(mock_entry.api.bootstrap)
    new_camera = camera[0].copy()
    new_camera.is_recording = True

    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.new_obj = new_camera

    new_bootstrap.cameras = {new_camera.id: new_camera}
    mock_entry.api.bootstrap = new_bootstrap
    mock_entry.api.ws_subscription(mock_msg)
    await hass.async_block_till_done()

    state = hass.states.get(camera[1])
    assert state and state.state == "recording"


async def test_camera_ws_update_offline(
    hass: HomeAssistant,
    mock_entry: MockEntityFixture,
    camera: tuple[ProtectCamera, str],
):
    """WS updates marks camera unavailable."""

    state = hass.states.get(camera[1])
    assert state and state.state == "idle"

    # camera goes offline
    new_bootstrap = copy(mock_entry.api.bootstrap)
    new_camera = camera[0].copy()
    new_camera.state = StateType.DISCONNECTED

    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.new_obj = new_camera

    new_bootstrap.cameras = {new_camera.id: new_camera}
    mock_entry.api.bootstrap = new_bootstrap
    mock_entry.api.ws_subscription(mock_msg)
    await hass.async_block_till_done()

    state = hass.states.get(camera[1])
    assert state and state.state == "unavailable"

    # camera comes back online
    new_camera.state = StateType.CONNECTED

    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.new_obj = new_camera

    new_bootstrap.cameras = {new_camera.id: new_camera}
    mock_entry.api.bootstrap = new_bootstrap
    mock_entry.api.ws_subscription(mock_msg)
    await hass.async_block_till_done()

    state = hass.states.get(camera[1])
    assert state and state.state == "idle"


async def test_camera_enable_motion(
    hass: HomeAssistant,
    mock_entry: MockEntityFixture,
    camera: tuple[ProtectCamera, str],
):
    """Tests generic entity update service."""

    camera[0].__fields__["set_motion_detection"] = Mock()
    camera[0].set_motion_detection = AsyncMock()

    await hass.services.async_call(
        "camera",
        "enable_motion_detection",
        {ATTR_ENTITY_ID: camera[1]},
        blocking=True,
    )

    camera[0].set_motion_detection.assert_called_once_with(True)


async def test_camera_disable_motion(
    hass: HomeAssistant,
    mock_entry: MockEntityFixture,
    camera: tuple[ProtectCamera, str],
):
    """Tests generic entity update service."""

    camera[0].__fields__["set_motion_detection"] = Mock()
    camera[0].set_motion_detection = AsyncMock()

    await hass.services.async_call(
        "camera",
        "disable_motion_detection",
        {ATTR_ENTITY_ID: camera[1]},
        blocking=True,
    )

    camera[0].set_motion_detection.assert_called_once_with(False)
