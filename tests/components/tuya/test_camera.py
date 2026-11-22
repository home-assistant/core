"""Test Tuya camera platform."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion
from tuya_sharing import CustomerDevice, Manager

from homeassistant.components.camera import (
    DOMAIN as CAMERA_DOMAIN,
    CameraService,
    get_camera_from_entity_id,
)
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
    ("outputs", "available", "expect_new_source"),
    [
        ({"hls": object()}, True, False),
        ({}, True, True),
        ({"hls": object()}, False, True),
    ],
)
async def test_stream_source_reallocated_after_idle_or_failure(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    outputs: dict[str, object],
    available: bool,
    expect_new_source: bool,
) -> None:
    """Keep working viewers but obtain a fresh Tuya allocation on a new start."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)
    camera = get_camera_from_entity_id(hass, "camera.burocam")
    mock_manager.get_device_stream_allocate.side_effect = [
        "rtsps://example.com/first",
        "rtsps://example.com/second",
    ]
    first_stream = MagicMock()
    first_stream.outputs.return_value = outputs
    first_stream.available = available
    first_stream.stop = AsyncMock()
    second_stream = MagicMock()
    second_stream.stop = AsyncMock()

    with patch(
        "homeassistant.components.camera.entity.create_stream",
        side_effect=[first_stream, second_stream],
    ) as create_stream:
        assert await camera.async_create_stream() is first_stream
        result = await camera.async_create_stream()

    if expect_new_source:
        assert result is second_stream
        first_stream.stop.assert_awaited_once()
        assert create_stream.call_count == 2
        assert create_stream.call_args.args[1] == "rtsps://example.com/second"
        assert mock_manager.get_device_stream_allocate.call_count == 2
    else:
        assert result is first_stream
        first_stream.stop.assert_not_awaited()
        assert create_stream.call_count == 1
        assert mock_manager.get_device_stream_allocate.call_count == 1


@pytest.mark.parametrize("mock_device_code", ["sp_rudejjigkywujjvs"])
async def test_snapshot_uses_new_tuya_allocation(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
) -> None:
    """Snapshots continue to use independent camera stream allocations."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)
    camera = get_camera_from_entity_id(hass, "camera.burocam")
    mock_manager.get_device_stream_allocate.side_effect = [
        "rtsps://example.com/snapshot1",
        "rtsps://example.com/snapshot2",
    ]
    with patch(
        "homeassistant.components.tuya.camera.ffmpeg.async_get_image",
        new_callable=AsyncMock,
        return_value=b"test-jpeg",
    ) as get_image:
        assert await camera.async_camera_image() == b"test-jpeg"
        assert await camera.async_camera_image() == b"test-jpeg"

    assert get_image.await_count == 2
    assert get_image.await_args_list[0].args[1] == "rtsps://example.com/snapshot1"
    assert get_image.await_args_list[1].args[1] == "rtsps://example.com/snapshot2"
