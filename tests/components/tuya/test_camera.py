"""Test Tuya camera platform."""

from threading import Thread
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
from homeassistant.components.camera.prefs import DynamicStreamSettings
from homeassistant.components.stream import Stream
from homeassistant.components.stream.core import StreamSettings
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


def _test_stream(hass: HomeAssistant, source: str, *, preload: bool = False) -> Stream:
    """Create a real stream without starting a media worker."""
    return Stream(
        hass,
        source,
        pyav_options={},
        stream_settings=StreamSettings(
            ll_hls=True,
            min_segment_duration=2,
            part_target_duration=0.5,
            hls_advance_part_limit=3,
            hls_part_timeout=10,
        ),
        dynamic_stream_settings=DynamicStreamSettings(preload_stream=preload),
    )


@pytest.mark.parametrize("mock_device_code", ["sp_rudejjigkywujjvs"])
@pytest.mark.parametrize(
    ("outputs", "available", "expected_allocations"),
    [
        ({"hls": object()}, True, 1),
        ({}, True, 2),
        ({"hls": object()}, False, 2),
    ],
)
async def test_stream_source_refresh_reuses_registered_stream(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    outputs: dict[str, object],
    available: bool,
    expected_allocations: int,
) -> None:
    """Reuse the same Stream on reopen, keeping its registry size bounded."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)
    camera = get_camera_from_entity_id(hass, "camera.burocam")
    mock_manager.get_device_stream_allocate.side_effect = [
        "rtsps://example.com/first",
        "rtsps://example.com/second",
        "rtsps://example.com/third",
    ]
    created: list[Stream] = []

    def create_test_stream(hass: HomeAssistant, source: str, **_kwargs: Any) -> Stream:
        stream = _test_stream(hass, source)
        created.append(stream)
        return stream

    with patch(
        "homeassistant.components.camera.entity.create_stream",
        side_effect=create_test_stream,
    ):
        stream = await camera.async_create_stream()
        assert stream is not None
        stream._outputs.update(outputs)
        stream._available = available
        assert await camera.async_create_stream() is stream

        if expected_allocations == 2:
            assert stream.source == "rtsps://example.com/second"
            # Multiple idle reopens must never add more Stream objects.
            stream._outputs.clear()
            assert await camera.async_create_stream() is stream
            assert stream.source == "rtsps://example.com/third"
        else:
            assert stream.source == "rtsps://example.com/first"

    assert len(created) == 1
    assert mock_manager.get_device_stream_allocate.call_count == (
        3 if expected_allocations == 2 else 1
    )


@pytest.mark.parametrize("mock_device_code", ["sp_rudejjigkywujjvs"])
async def test_failed_preloaded_stream_worker_is_stopped_before_refresh(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
) -> None:
    """Stop the actual worker even if Stream.stop would keep it running."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)
    camera = get_camera_from_entity_id(hass, "camera.burocam")
    mock_manager.get_device_stream_allocate.side_effect = [
        "rtsps://example.com/first",
        "rtsps://example.com/second",
    ]
    stream = _test_stream(hass, "rtsps://example.com/first", preload=True)

    with patch(
        "homeassistant.components.camera.entity.create_stream",
        return_value=stream,
    ):
        assert await camera.async_create_stream() is stream

        # A preloaded stream may have an active worker retrying an expired URL.
        # Run a real thread that waits for the worker's shutdown signal.
        stream._outputs["hls"] = MagicMock()
        worker = Thread(target=stream._thread_quit.wait, daemon=True)
        stream._thread = worker
        worker.start()
        stream._available = False

        try:
            assert await camera.async_create_stream() is stream
            assert not worker.is_alive()
            assert stream._thread is None
            assert stream.source == "rtsps://example.com/second"
            assert stream.dynamic_stream_settings.preload_stream
        finally:
            stream._thread_quit.set()
            await hass.async_add_executor_job(worker.join)

    assert mock_manager.get_device_stream_allocate.call_count == 2


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
