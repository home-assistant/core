"""Tests for BoschCamera's LOCAL-only live-stream wiring (local_stream.py glue)."""

import asyncio
from unittest.mock import AsyncMock, patch

from homeassistant.components.camera import CameraEntityFeature
from homeassistant.core import HomeAssistant

from .test_camera import _setup_camera_entity

_CAMERA_MOD = "homeassistant.components.bosch_shc_camera.camera"


async def test_snapshot_only_by_default(hass: HomeAssistant) -> None:
    """With the LOCAL-stream start mocked to fail, the entity stays snapshot-only."""
    entity = await _setup_camera_entity(hass)
    assert entity.supported_features == CameraEntityFeature(0)
    assert await entity.stream_source() is None


async def test_successful_local_stream_advertises_stream_feature(
    hass: HomeAssistant, mock_local_stream_start: AsyncMock
) -> None:
    """A successful LOCAL session sets stream_source() and CameraEntityFeature.STREAM."""
    mock_local_stream_start.return_value = (
        "rtsp://user:pass@127.0.0.1:12345/rtsp_tunnel"
    )
    entity = await _setup_camera_entity(hass)

    assert entity.supported_features & CameraEntityFeature.STREAM
    assert (
        await entity.stream_source() == "rtsp://user:pass@127.0.0.1:12345/rtsp_tunnel"
    )


async def test_local_stream_setup_exception_leaves_entity_snapshot_only(
    hass: HomeAssistant, mock_local_stream_start: AsyncMock
) -> None:
    """An unexpected exception from local_stream.py must never crash entity setup."""
    mock_local_stream_start.side_effect = RuntimeError("boom")
    entity = await _setup_camera_entity(hass)

    assert entity.supported_features == CameraEntityFeature(0)
    assert await entity.stream_source() is None


async def test_on_local_stream_died_withdraws_streaming(hass: HomeAssistant) -> None:
    """The TLS proxy's circuit-breaker callback clears the URL and STREAM feature."""
    entity = await _setup_camera_entity(hass)
    entity._rtsp_url = "rtsp://user:pass@127.0.0.1:12345/rtsp_tunnel"
    entity._attr_supported_features = CameraEntityFeature.STREAM

    entity._on_local_stream_died()

    assert entity._rtsp_url is None
    assert entity.supported_features == CameraEntityFeature(0)


async def test_unload_cancels_stream_start_task_and_stops_proxy(
    hass: HomeAssistant, mock_local_stream_start: AsyncMock
) -> None:
    """Removing the entity cancels a still-pending stream-start task and stops the proxy."""
    entity = await _setup_camera_entity(hass)

    async def _never_finishes(*_args: object, **_kwargs: object) -> str | None:
        await asyncio.sleep(3600)
        return None

    mock_local_stream_start.side_effect = _never_finishes
    task = hass.async_create_task(entity._async_start_local_stream())
    entity._stream_start_task = task
    await asyncio.sleep(0)  # let the task actually start (enter the sleep)

    with patch(f"{_CAMERA_MOD}.async_stop_local_stream", AsyncMock()) as mock_stop:
        await entity.async_will_remove_from_hass()
        await hass.async_block_till_done()

    assert task.cancelled()
    mock_stop.assert_awaited_once_with(
        entity._cam_id, entity._tls_proxy_ports, entity._tls_proxy_servers
    )


async def test_unload_stops_proxy_even_when_stream_start_already_finished(
    hass: HomeAssistant,
) -> None:
    """A LOCAL session that's already up still has its proxy stopped on unload."""
    entity = await _setup_camera_entity(hass)
    entity._rtsp_url = "rtsp://user:pass@127.0.0.1:12345/rtsp_tunnel"

    with patch(f"{_CAMERA_MOD}.async_stop_local_stream", AsyncMock()) as mock_stop:
        await entity.async_will_remove_from_hass()

    mock_stop.assert_awaited_once_with(
        entity._cam_id, entity._tls_proxy_ports, entity._tls_proxy_servers
    )
