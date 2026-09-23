"""Tests for the EZVIZ camera platform."""

import asyncio
from collections.abc import Generator
import logging
import sys
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import urlparse

from pyezvizapi.exceptions import PyEzvizError
import pytest

from homeassistant.components.camera import (
    DATA_COMPONENT,
    CameraEntityFeature,
    async_get_image,
    async_get_stream_source,
)
from homeassistant.components.ffmpeg import DATA_FFMPEG, FFmpegManager
from homeassistant.const import ATTR_SUPPORTED_FEATURES
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import setup_integration
from .test_init import _mock_camera_data

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator

SERIAL = "C123456789"
ENTITY_ID = "camera.camera_1"
ALARM_PIC_URL = "https://example.com/alarm.jpg"

# Stands in for FFmpeg: copies stdin to stdout, like a codec-copy remux.
_CAT = "import shutil, sys; shutil.copyfileobj(sys.stdin.buffer, sys.stdout.buffer)"


@pytest.fixture(autouse=True)
def mock_ffmpeg_manager(hass: HomeAssistant) -> None:
    """Provide the FFmpeg manager the camera entities need."""
    hass.data[DATA_FFMPEG] = FFmpegManager(hass, "ffmpeg")


@pytest.fixture
def mock_ffmpeg_process() -> Generator[None]:
    """Replace the FFmpeg remux process with a stdin to stdout copy."""
    create_subprocess_exec = asyncio.create_subprocess_exec

    async def _exec(*_args: str, **kwargs: object) -> asyncio.subprocess.Process:
        return await create_subprocess_exec(sys.executable, "-c", _CAT, **kwargs)

    with patch(
        "homeassistant.components.ezviz.vtm.asyncio.create_subprocess_exec",
        side_effect=_exec,
    ):
        yield


def _packet(body: bytes, *, encrypted: bool = False) -> MagicMock:
    """Return a mocked VTM stream packet."""
    return MagicMock(body=body, encrypted=encrypted)


def _mock_cloud_stream(packets: list[MagicMock]) -> MagicMock:
    """Return a mocked open_cloud_stream context manager yielding packets."""
    stream = MagicMock()
    stream.iter_packets.return_value = iter(packets)
    cloud_stream = MagicMock()
    cloud_stream.__enter__.return_value = stream
    return cloud_stream


async def _setup_vtm_camera(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_ezviz_client: AsyncMock,
    **data: object,
) -> None:
    """Set up a camera whose device reports no local RTSP server."""
    mock_ezviz_client.load_cameras.return_value = {
        SERIAL: _mock_camera_data(CONNECTION={"localRtspPort": 0}, **data)
    }
    await setup_integration(hass, mock_config_entry)


async def test_vtm_stream_source_without_rtsp(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_ezviz_client: AsyncMock,
) -> None:
    """Test devices without RTSP stream through the local VTM view."""
    await _setup_vtm_camera(hass, mock_config_entry, mock_ezviz_client)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == CameraEntityFeature.STREAM

    source = await async_get_stream_source(hass, ENTITY_ID)
    assert source is not None
    url = urlparse(source)
    assert url.hostname == "127.0.0.1"
    assert url.path.startswith("/api/ezviz/vtm/")
    assert url.path.endswith(f"/{SERIAL}.ts")

    # No RTSP credentials are needed, so no discovery flow asks for them.
    assert not hass.config_entries.flow.async_progress()


async def test_rtsp_camera_without_credentials_uses_vtm(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_ezviz_client: AsyncMock,
) -> None:
    """Test RTSP devices without credentials still get a stream and a prompt."""
    mock_ezviz_client.load_cameras.return_value = {
        SERIAL: _mock_camera_data(CONNECTION={"localRtspPort": 554})
    }
    await setup_integration(hass, mock_config_entry)

    source = await async_get_stream_source(hass, ENTITY_ID)
    assert source is not None
    assert urlparse(source).path.endswith(f"/{SERIAL}.ts")
    assert len(hass.config_entries.flow.async_progress()) == 1


async def test_vtm_view_streams_relay(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_ezviz_client: AsyncMock,
    mock_ffmpeg_process: None,
) -> None:
    """Test the view copies the relay payloads through the remux process."""
    await _setup_vtm_camera(hass, mock_config_entry, mock_ezviz_client)
    path = urlparse(await async_get_stream_source(hass, ENTITY_ID)).path
    client = await hass_client_no_auth()

    cloud_stream = _mock_cloud_stream(
        [_packet(b"\x00\x00\x01\xba"), _packet(b""), _packet(b"payload")]
    )
    with patch(
        "homeassistant.components.ezviz.vtm.open_cloud_stream",
        return_value=cloud_stream,
    ) as mock_open:
        response = await client.get(path)
        assert response.status == 200
        assert response.headers["Content-Type"] == "video/MP2T"
        assert await response.read() == b"\x00\x00\x01\xbapayload"

    mock_open.assert_called_once_with(mock_ezviz_client, SERIAL)
    cloud_stream.__enter__.return_value.start.assert_called_once()


async def test_vtm_view_stops_on_encrypted_stream(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_ezviz_client: AsyncMock,
    mock_ffmpeg_process: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test encrypted relay packets end the stream with an error."""
    await _setup_vtm_camera(hass, mock_config_entry, mock_ezviz_client)
    path = urlparse(await async_get_stream_source(hass, ENTITY_ID)).path
    client = await hass_client_no_auth()

    with patch(
        "homeassistant.components.ezviz.vtm.open_cloud_stream",
        return_value=_mock_cloud_stream(
            [_packet(b"secret", encrypted=True), _packet(b"never")]
        ),
    ):
        response = await client.get(path)
        assert await response.read() == b""

    assert "VTM stream is encrypted" in caplog.text


async def test_vtm_view_relay_error(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_ezviz_client: AsyncMock,
    mock_ffmpeg_process: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a failing relay ends the stream and is logged."""
    await _setup_vtm_camera(hass, mock_config_entry, mock_ezviz_client)
    path = urlparse(await async_get_stream_source(hass, ENTITY_ID)).path
    client = await hass_client_no_auth()

    with (
        caplog.at_level(logging.WARNING),
        patch(
            "homeassistant.components.ezviz.vtm.open_cloud_stream",
            side_effect=PyEzvizError("no relay"),
        ),
    ):
        response = await client.get(path)
        assert await response.read() == b""

    assert "VTM stream failed: no relay" in caplog.text


@pytest.mark.parametrize(
    "path",
    [
        f"/api/ezviz/vtm/wrong-token/{SERIAL}.ts",
        "/api/ezviz/vtm/{token}/C000000000.ts",
    ],
)
async def test_vtm_view_not_found(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_ezviz_client: AsyncMock,
    path: str,
) -> None:
    """Test the view rejects a wrong access token or an unknown serial."""
    await _setup_vtm_camera(hass, mock_config_entry, mock_ezviz_client)
    token = urlparse(await async_get_stream_source(hass, ENTITY_ID)).path.split("/")[4]
    client = await hass_client_no_auth()

    with patch("homeassistant.components.ezviz.vtm.open_cloud_stream") as mock_open:
        response = await client.get(path.format(token=token))

    assert response.status == 404
    mock_open.assert_not_called()


async def test_vtm_camera_image_uses_last_alarm_picture(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_ezviz_client: AsyncMock,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test still images do not open the relay and wake the device."""
    aioclient_mock.get(ALARM_PIC_URL, content=b"alarm-jpeg")
    await _setup_vtm_camera(
        hass, mock_config_entry, mock_ezviz_client, last_alarm_pic=ALARM_PIC_URL
    )

    with patch("homeassistant.components.ezviz.vtm.open_cloud_stream") as mock_open:
        image = await async_get_image(hass, ENTITY_ID)

    assert image.content == b"alarm-jpeg"
    mock_open.assert_not_called()


async def test_vtm_camera_image_from_running_stream(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_ezviz_client: AsyncMock,
) -> None:
    """Test still images come from the running stream when there is one."""
    await _setup_vtm_camera(
        hass, mock_config_entry, mock_ezviz_client, last_alarm_pic=ALARM_PIC_URL
    )
    camera = hass.data[DATA_COMPONENT].get_entity(ENTITY_ID)
    assert camera is not None
    camera.stream = MagicMock(async_get_image=AsyncMock(return_value=b"keyframe"))

    image = await async_get_image(hass, ENTITY_ID)

    assert image.content == b"keyframe"


@pytest.mark.parametrize(
    ("last_alarm_pic", "status"),
    [(None, 200), (ALARM_PIC_URL, 404)],
    ids=["no_alarm_picture", "download_error"],
)
async def test_vtm_camera_image_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_ezviz_client: AsyncMock,
    aioclient_mock: AiohttpClientMocker,
    last_alarm_pic: str | None,
    status: int,
) -> None:
    """Test no still image without a stream or a usable alarm picture."""
    aioclient_mock.get(ALARM_PIC_URL, status=status)
    await _setup_vtm_camera(
        hass, mock_config_entry, mock_ezviz_client, last_alarm_pic=last_alarm_pic
    )

    with pytest.raises(HomeAssistantError):
        await async_get_image(hass, ENTITY_ID)


@pytest.mark.parametrize(
    ("decrypt_side_effect", "expected"),
    [(None, b"decrypted"), (PyEzvizError("wrong key"), b"encrypted")],
)
async def test_vtm_camera_image_decrypts_alarm_picture(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_camera_config_entry: MockConfigEntry,
    mock_ezviz_client: AsyncMock,
    aioclient_mock: AiohttpClientMocker,
    decrypt_side_effect: Exception | None,
    expected: bytes,
) -> None:
    """Test encrypted alarm pictures are decrypted with the camera password."""
    aioclient_mock.get(ALARM_PIC_URL, content=b"encrypted")
    mock_camera_config_entry.add_to_hass(hass)
    mock_ezviz_client.load_cameras.return_value = {
        "C666666": _mock_camera_data(
            CONNECTION={"localRtspPort": 0},
            encrypted=True,
            last_alarm_pic=ALARM_PIC_URL,
        )
    }
    await setup_integration(hass, mock_config_entry)

    with patch(
        "homeassistant.components.ezviz.camera.decrypt_image",
        return_value=b"decrypted",
        side_effect=decrypt_side_effect,
    ) as mock_decrypt:
        image = await async_get_image(hass, ENTITY_ID)

    mock_decrypt.assert_called_once_with(b"encrypted", "test-password")
    assert image.content == expected
