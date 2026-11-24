"""Test Tuya camera platform."""

import asyncio
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion
from tuya_sharing import CustomerDevice, Manager

from homeassistant.components.camera import (
    DOMAIN as CAMERA_DOMAIN,
    CameraService,
    get_camera_from_entity_id,
)
from homeassistant.components.stream import Stream
from homeassistant.const import Platform, TargetKey
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import initialize_entry


@pytest.fixture(autouse=True)
def platform_autouse():
    """Platform fixture."""
    with (
        patch("homeassistant.components.tuya.PLATFORMS", [Platform.CAMERA]),
        # Mock camera access token which normally is randomized.
        patch(
            "homeassistant.components.camera.entity.SystemRandom.getrandbits",
            return_value=1,
        ),
    ):
        yield


@pytest.mark.usefixtures("no_quirk")
async def test_platform_setup_and_discovery(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_devices: list[CustomerDevice],
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test platform setup and discovery."""

    await initialize_entry(hass, mock_manager, mock_config_entry, mock_devices)

    await snapshot_platform(
        hass,
        entity_registry,
        snapshot,
        mock_config_entry.entry_id,
    )


@pytest.mark.parametrize(
    "mock_device_code",
    ["sp_rudejjigkywujjvs"],
)
@pytest.mark.parametrize(
    ("service", "expected_command"),
    [
        (
            CameraService.DISABLE_MOTION_DETECTION,
            {"code": "motion_switch", "value": False},
        ),
        (
            CameraService.ENABLE_MOTION_DETECTION,
            {"code": "motion_switch", "value": True},
        ),
    ],
)
async def test_action(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    service: str,
    expected_command: dict[str, Any],
) -> None:
    """Test camera action."""
    entity_id = "camera.burocam"
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    state = hass.states.get(entity_id)
    assert state is not None, f"{entity_id} does not exist"
    await hass.services.async_call(
        CAMERA_DOMAIN,
        service,
        {
            TargetKey.ENTITY_ID: entity_id,
        },
        blocking=True,
    )
    mock_manager.send_commands.assert_called_once_with(
        mock_device.id, [expected_command]
    )


@pytest.mark.parametrize("mock_device_code", ["sp_rudejjigkywujjvs"])
@pytest.mark.parametrize(
    ("has_output", "available", "expect_refresh"),
    [
        pytest.param(True, True, False, id="active"),
        pytest.param(False, True, True, id="idle"),
        pytest.param(True, False, True, id="failed"),
    ],
)
async def test_camera_stream_source_refresh(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    has_output: bool,
    available: bool,
    expect_refresh: bool,
) -> None:
    """Refresh idle or failed Tuya URLs, but keep a healthy active stream."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)
    camera = get_camera_from_entity_id(hass, "camera.burocam")
    mock_manager.get_device_stream_allocate.side_effect = [
        "rtsps://example.com/initial",
        "rtsps://example.com/refreshed",
    ]
    stream = MagicMock(spec=Stream)
    stream.outputs.return_value = {"hls": object()} if has_output else {}
    stream.available = available

    with patch(
        "homeassistant.components.camera.entity.create_stream", return_value=stream
    ):
        assert await camera.async_create_stream() is stream
        assert await camera.async_create_stream() is stream

    if expect_refresh:
        stream.update_source.assert_called_once_with("rtsps://example.com/refreshed")
    else:
        stream.update_source.assert_not_called()
    assert mock_manager.get_device_stream_allocate.call_count == (
        2 if expect_refresh else 1
    )


@pytest.mark.parametrize("mock_device_code", ["sp_rudejjigkywujjvs"])
async def test_camera_stream_refresh_without_source(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
) -> None:
    """Return None instead of trying an expired URL when Tuya returns no URL."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)
    camera = get_camera_from_entity_id(hass, "camera.burocam")
    mock_manager.get_device_stream_allocate.side_effect = [
        "rtsps://example.com/initial",
        None,
    ]
    stream = MagicMock(spec=Stream)
    stream.outputs.return_value = {}

    with patch(
        "homeassistant.components.camera.entity.create_stream", return_value=stream
    ):
        assert await camera.async_create_stream() is stream
        assert await camera.async_create_stream() is None

    stream.update_source.assert_not_called()
    assert mock_manager.get_device_stream_allocate.call_count == 2


@pytest.mark.parametrize("mock_device_code", ["sp_rudejjigkywujjvs"])
async def test_camera_stream_refresh_timeout(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
) -> None:
    """Bound the time waiting for Tuya to allocate a replacement source."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)
    camera = get_camera_from_entity_id(hass, "camera.burocam")
    mock_manager.get_device_stream_allocate.return_value = "rtsps://example.com/initial"
    stream = MagicMock(spec=Stream)
    stream.outputs.return_value = {}

    async def stalled_source() -> str:
        await asyncio.Event().wait()
        return "rtsps://example.com/never"

    with patch(
        "homeassistant.components.camera.entity.create_stream", return_value=stream
    ):
        assert await camera.async_create_stream() is stream
        with (
            patch.object(camera, "stream_source", side_effect=stalled_source),
            patch("homeassistant.components.tuya.camera.STREAM_SOURCE_TIMEOUT", 0.05),
            pytest.raises(TimeoutError),
        ):
            await camera.async_create_stream()

    stream.update_source.assert_not_called()
