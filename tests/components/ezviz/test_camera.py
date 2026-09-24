"""Tests for the EZVIZ camera platform."""

import asyncio
from collections.abc import Generator
import logging
import sys
import threading
from typing import Any
from unittest.mock import ANY, AsyncMock, MagicMock, patch
from urllib.parse import parse_qs, urlparse

from aiohttp import ClientError, ClientPayloadError
from pyezvizapi.exceptions import PyEzvizError
import pytest

from homeassistant.components.camera import (
    DATA_COMPONENT,
    CameraEntityFeature,
    async_get_image,
    async_get_stream_source,
)
from homeassistant.components.ezviz.vtm import DATA_VTM
from homeassistant.components.ffmpeg import DATA_FFMPEG, FFmpegManager
from homeassistant.components.stream import redact_credentials
from homeassistant.const import ATTR_SUPPORTED_FEATURES
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.network import NoURLAvailableError

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


def _local_url(source: str | None) -> str:
    """Return the path and query of a stream source for the test client."""
    assert source is not None
    url = urlparse(source)
    return f"{url.path}?{url.query}"


def _token(source: str | None) -> str:
    """Return the access token of a stream source."""
    assert source is not None
    return parse_qs(urlparse(source).query)["auth"][0]


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
    hass.config.internal_url = "http://ha.local:8123"
    await _setup_vtm_camera(hass, mock_config_entry, mock_ezviz_client)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == CameraEntityFeature.STREAM

    source = await async_get_stream_source(hass, ENTITY_ID)
    assert source is not None
    url = urlparse(source)
    assert f"{url.scheme}://{url.netloc}" == "http://ha.local:8123"
    assert url.path == f"/api/ezviz/vtm/{SERIAL}.ts"
    # The token is in a query parameter the stream integration redacts.
    assert _token(source) not in redact_credentials(source)
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
    path = _local_url(await async_get_stream_source(hass, ENTITY_ID))
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

    mock_open.assert_called_once_with(mock_ezviz_client, SERIAL, socket_factory=ANY)
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
    path = _local_url(await async_get_stream_source(hass, ENTITY_ID))
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
    path = _local_url(await async_get_stream_source(hass, ENTITY_ID))
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
        f"/api/ezviz/vtm/{SERIAL}.ts",
        f"/api/ezviz/vtm/{SERIAL}.ts?auth=wrong-token",
        "/api/ezviz/vtm/C000000000.ts?auth={token}",
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
    token = _token(await async_get_stream_source(hass, ENTITY_ID))
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
    camera.stream = MagicMock(
        outputs=MagicMock(return_value={"hls": MagicMock()}),
        async_get_image=AsyncMock(return_value=b"keyframe"),
    )

    image = await async_get_image(hass, ENTITY_ID)

    assert image.content == b"keyframe"


async def test_vtm_camera_image_does_not_restart_stopped_stream(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_ezviz_client: AsyncMock,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test a stopped stream is not restarted just for a still image."""
    aioclient_mock.get(ALARM_PIC_URL, content=b"alarm-jpeg")
    await _setup_vtm_camera(
        hass, mock_config_entry, mock_ezviz_client, last_alarm_pic=ALARM_PIC_URL
    )
    camera = hass.data[DATA_COMPONENT].get_entity(ENTITY_ID)
    assert camera is not None
    camera.stream = MagicMock(
        outputs=MagicMock(return_value={}), async_get_image=AsyncMock()
    )

    image = await async_get_image(hass, ENTITY_ID)

    assert image.content == b"alarm-jpeg"
    camera.stream.async_get_image.assert_not_called()


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


async def test_vtm_token_is_scoped_per_camera(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_ezviz_client: AsyncMock,
) -> None:
    """Test one camera's token cannot open another camera's stream."""
    mock_ezviz_client.load_cameras.return_value = {
        SERIAL: _mock_camera_data(CONNECTION={"localRtspPort": 0}),
        "C987654321": _mock_camera_data(
            name="Camera 2", CONNECTION={"localRtspPort": 0}
        ),
    }
    await setup_integration(hass, mock_config_entry)
    path = _local_url(await async_get_stream_source(hass, ENTITY_ID))
    other = await async_get_stream_source(hass, "camera.camera_2")
    assert _token(path) != _token(other)
    client = await hass_client_no_auth()

    with patch("homeassistant.components.ezviz.vtm.open_cloud_stream") as mock_open:
        response = await client.get(path.replace(SERIAL, "C987654321"))

    assert response.status == 404
    mock_open.assert_not_called()


async def test_vtm_view_unregistered_on_unload(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_ezviz_client: AsyncMock,
) -> None:
    """Test stream URLs stop working once the config entry unloads."""
    await _setup_vtm_camera(hass, mock_config_entry, mock_ezviz_client)
    path = _local_url(await async_get_stream_source(hass, ENTITY_ID))
    client = await hass_client_no_auth()

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    with patch("homeassistant.components.ezviz.vtm.open_cloud_stream") as mock_open:
        response = await client.get(path)

    assert response.status == 404
    mock_open.assert_not_called()


async def test_vtm_relay_socket_shut_down_after_stream(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_ezviz_client: AsyncMock,
    mock_ffmpeg_process: None,
) -> None:
    """Test the relay socket is shut down when the stream ends."""
    await _setup_vtm_camera(hass, mock_config_entry, mock_ezviz_client)
    path = _local_url(await async_get_stream_source(hass, ENTITY_ID))
    client = await hass_client_no_auth()
    sock = MagicMock()

    def _open(*_args: object, socket_factory: Any) -> MagicMock:
        assert socket_factory(("vtm.example.com", 8554), 10.0) is sock
        return _mock_cloud_stream([_packet(b"payload")])

    with (
        patch(
            "homeassistant.components.ezviz.vtm.socket.create_connection",
            return_value=sock,
        ),
        patch(
            "homeassistant.components.ezviz.vtm.open_cloud_stream", side_effect=_open
        ),
    ):
        response = await client.get(path)
        assert await response.read() == b"payload"

    sock.shutdown.assert_called_once()


async def test_vtm_view_small_queue_keeps_all_payloads(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_ezviz_client: AsyncMock,
    mock_ffmpeg_process: None,
) -> None:
    """Test the bounded relay queue applies backpressure without dropping data."""
    await _setup_vtm_camera(hass, mock_config_entry, mock_ezviz_client)
    path = _local_url(await async_get_stream_source(hass, ENTITY_ID))
    client = await hass_client_no_auth()
    payloads = [bytes([i]) * 100 for i in range(50)]

    with (
        patch("homeassistant.components.ezviz.vtm.QUEUE_SIZE", 1),
        patch(
            "homeassistant.components.ezviz.vtm.open_cloud_stream",
            return_value=_mock_cloud_stream([_packet(p) for p in payloads]),
        ),
    ):
        response = await client.get(path)
        assert await response.read() == b"".join(payloads)


async def test_rtsp_camera_not_exposed_through_vtm_view(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_camera_config_entry: MockConfigEntry,
    mock_ezviz_client: AsyncMock,
) -> None:
    """Test cameras streaming over RTSP are not registered for the view."""
    mock_camera_config_entry.add_to_hass(hass)
    mock_ezviz_client.load_cameras.return_value = {
        "C666666": _mock_camera_data(CONNECTION={"localRtspPort": 554})
    }
    await setup_integration(hass, mock_config_entry)

    source = await async_get_stream_source(hass, ENTITY_ID)
    assert source == (
        "rtsp://test-username:test-password@192.168.1.100:554/Streaming/Channels/102"
    )
    assert "C666666" not in hass.data.get(DATA_VTM, {})


async def test_vtm_stream_source_without_internal_url(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_ezviz_client: AsyncMock,
) -> None:
    """Test there is no stream source when HA has no internal URL."""
    await _setup_vtm_camera(hass, mock_config_entry, mock_ezviz_client)

    with patch(
        "homeassistant.components.ezviz.vtm.get_url",
        side_effect=NoURLAvailableError,
    ):
        assert await async_get_stream_source(hass, ENTITY_ID) is None


async def test_vtm_unload_ends_running_stream(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_ezviz_client: AsyncMock,
    mock_ffmpeg_process: None,
) -> None:
    """Test unloading the config entry ends streams that are still running."""
    await _setup_vtm_camera(hass, mock_config_entry, mock_ezviz_client)
    path = _local_url(await async_get_stream_source(hass, ENTITY_ID))
    client = await hass_client_no_auth()
    streaming = threading.Event()
    release = threading.Event()

    def _packets() -> Generator[MagicMock]:
        yield _packet(b"first")
        streaming.set()
        release.wait(10)

    cloud_stream = MagicMock()
    cloud_stream.__enter__.return_value.iter_packets.return_value = _packets()

    with patch(
        "homeassistant.components.ezviz.vtm.open_cloud_stream",
        return_value=cloud_stream,
    ):
        request = asyncio.create_task(client.get(path))
        assert await hass.async_add_executor_job(streaming.wait, 10)
        camera = hass.data[DATA_VTM][SERIAL]
        assert camera.streams

        await hass.config_entries.async_unload(mock_config_entry.entry_id)
        release.set()
        response = await request
        with pytest.raises(ClientPayloadError):
            await response.read()

    assert not camera.streams
    assert SERIAL not in hass.data[DATA_VTM]


async def test_vtm_unload_while_ffmpeg_starts(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_ezviz_client: AsyncMock,
) -> None:
    """Test unloading during stream setup cancels the request before the relay."""
    await _setup_vtm_camera(hass, mock_config_entry, mock_ezviz_client)
    path = _local_url(await async_get_stream_source(hass, ENTITY_ID))
    client = await hass_client_no_auth()
    starting = asyncio.Event()

    async def _pending_exec(*_args: object, **_kwargs: object) -> None:
        starting.set()
        await asyncio.Event().wait()

    with (
        patch(
            "homeassistant.components.ezviz.vtm.asyncio.create_subprocess_exec",
            side_effect=_pending_exec,
        ),
        patch("homeassistant.components.ezviz.vtm.open_cloud_stream") as mock_open,
    ):
        request = asyncio.create_task(client.get(path))
        await starting.wait()
        camera = hass.data[DATA_VTM][SERIAL]
        assert camera.streams

        await hass.config_entries.async_unload(mock_config_entry.entry_id)
        with pytest.raises(ClientError):
            await request

    assert not camera.streams
    mock_open.assert_not_called()
