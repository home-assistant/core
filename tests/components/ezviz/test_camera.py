"""Tests for the EZVIZ camera platform."""

import asyncio
import logging
import threading
from unittest.mock import ANY, AsyncMock, MagicMock, patch
from urllib.parse import parse_qs, urlparse

from aiohttp import ClientError, ClientPayloadError
from pyezvizapi.exceptions import PyEzvizError
import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker
from pytest_homeassistant.typing import ClientSessionGenerator

from homeassistant.components.camera import (
    DATA_COMPONENT,
    CameraEntityFeature,
    async_get_image,
    async_get_stream_source,
)
from homeassistant.components.ezviz.vtm import DATA_VTM, STARTUP_TIMEOUT
from homeassistant.components.ffmpeg import DATA_FFMPEG, FFmpegManager
from homeassistant.components.stream import redact_credentials
from homeassistant.const import ATTR_SUPPORTED_FEATURES
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.network import NoURLAvailableError

from . import setup_integration
from .test_init import _mock_camera_data

SERIAL = "C123456789"
ENTITY_ID = "camera.camera_1"
ALARM_PIC_URL = "https://example.com/alarm.jpg"
OPEN_STREAM = "homeassistant.components.ezviz.vtm.open_live_mpegts_stream"


class FakeLiveStream:
    """Stand-in for the pyezvizapi live MPEG-TS stream."""

    def __init__(
        self,
        chunks: list[bytes] | None = None,
        *,
        read_error: Exception | None = None,
        close_error: Exception | None = None,
        block: bool = False,
    ) -> None:
        """Initialize the fake stream."""
        self._chunks = list(chunks or [])
        self._read_error = read_error
        self._close_error = close_error
        self._block = block
        self.reading = threading.Event()
        self.closed = threading.Event()

    def read(self, size: int) -> bytes:
        """Return the next chunk, then fail, block until closed, or end."""
        self.reading.set()
        if self._chunks:
            return self._chunks.pop(0)
        if self._read_error is not None:
            raise self._read_error
        if self._block:
            self.closed.wait(10)
        return b""

    def close(self) -> None:
        """Close the stream, like the library does from another thread."""
        self.closed.set()
        if self._close_error is not None:
            raise self._close_error


@pytest.fixture(autouse=True)
def mock_ffmpeg_manager(hass: HomeAssistant) -> None:
    """Provide the FFmpeg manager the camera entities need."""
    hass.data[DATA_FFMPEG] = FFmpegManager(hass, "ffmpeg")


def _local_url(source: str | None) -> str:
    """Return the path and query of a stream source for the test client."""
    assert source is not None
    url = urlparse(source)
    return f"{url.path}?{url.query}"


def _token(source: str | None) -> str:
    """Return the access token of a stream source."""
    assert source is not None
    return parse_qs(urlparse(source).query)["auth"][0]


async def _setup_vtm_camera(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_ezviz_client: AsyncMock,
    **data: object,
) -> None:
    """Set up a camera whose device reports no local RTSP port."""
    mock_ezviz_client.load_cameras.return_value = {
        SERIAL: _mock_camera_data(reported_local_rtsp_port=0, **data)
    }
    await setup_integration(hass, mock_config_entry)


async def test_vtm_stream_source_without_rtsp(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_ezviz_client: AsyncMock,
) -> None:
    """Test devices without RTSP stream through the local view."""
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

    # No RTSP credentials are needed, so no discovery flow asks for them.
    assert not hass.config_entries.flow.async_progress()


async def test_rtsp_camera_without_credentials_uses_vtm(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_ezviz_client: AsyncMock,
) -> None:
    """Test RTSP devices without credentials still get a stream and a prompt."""
    mock_ezviz_client.load_cameras.return_value = {
        SERIAL: _mock_camera_data(reported_local_rtsp_port=554)
    }
    await setup_integration(hass, mock_config_entry)

    source = await async_get_stream_source(hass, ENTITY_ID)
    assert source is not None
    assert urlparse(source).path.endswith(f"/{SERIAL}.ts")
    assert len(hass.config_entries.flow.async_progress()) == 1


async def test_rtsp_camera_not_exposed_through_vtm_view(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_camera_config_entry: MockConfigEntry,
    mock_ezviz_client: AsyncMock,
) -> None:
    """Test cameras streaming over RTSP are not registered for the view."""
    mock_camera_config_entry.add_to_hass(hass)
    mock_ezviz_client.load_cameras.return_value = {
        "C666666": _mock_camera_data(reported_local_rtsp_port=554)
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


async def test_vtm_view_streams_live_mpegts(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_ezviz_client: AsyncMock,
) -> None:
    """Test the view copies the library's MPEG-TS stream to the client."""
    await _setup_vtm_camera(hass, mock_config_entry, mock_ezviz_client)
    path = _local_url(await async_get_stream_source(hass, ENTITY_ID))
    client = await hass_client_no_auth()
    stream = FakeLiveStream([b"\x47first", b"\x47second"])

    with patch(OPEN_STREAM, return_value=stream) as mock_open:
        response = await client.get(path)
        assert response.status == 200
        assert response.headers["Content-Type"] == "video/MP2T"
        assert await response.read() == b"\x47first\x47second"

    mock_open.assert_called_once_with(
        mock_ezviz_client, SERIAL, ffmpeg_path="ffmpeg", source=ANY
    )
    source = mock_open.call_args.kwargs["source"]
    assert source.mode == "cloud"
    assert source.timeout == STARTUP_TIMEOUT
    assert stream.closed.is_set()


async def test_vtm_view_open_failure(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_ezviz_client: AsyncMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a stream that cannot be opened returns 503 and is logged."""
    await _setup_vtm_camera(hass, mock_config_entry, mock_ezviz_client)
    path = _local_url(await async_get_stream_source(hass, ENTITY_ID))
    client = await hass_client_no_auth()

    with patch(OPEN_STREAM, side_effect=PyEzvizError("no stream")):
        response = await client.get(path)

    assert response.status == 503
    assert "cannot open live stream: no stream" in caplog.text


async def test_vtm_view_stream_failure(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_ezviz_client: AsyncMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a stream failing mid-way ends the response, closes and logs."""
    await _setup_vtm_camera(hass, mock_config_entry, mock_ezviz_client)
    path = _local_url(await async_get_stream_source(hass, ENTITY_ID))
    client = await hass_client_no_auth()
    stream = FakeLiveStream([b"\x47data"], read_error=PyEzvizError("ffmpeg failed"))

    with caplog.at_level(logging.WARNING), patch(OPEN_STREAM, return_value=stream):
        response = await client.get(path)
        assert await response.read() == b"\x47data"

    assert "live stream failed: ffmpeg failed" in caplog.text
    assert stream.closed.is_set()


async def test_vtm_view_close_failure(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_ezviz_client: AsyncMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a teardown the library cannot confirm is logged."""
    await _setup_vtm_camera(hass, mock_config_entry, mock_ezviz_client)
    path = _local_url(await async_get_stream_source(hass, ENTITY_ID))
    client = await hass_client_no_auth()
    stream = FakeLiveStream(close_error=PyEzvizError("shutdown timed out"))

    with patch(OPEN_STREAM, return_value=stream):
        response = await client.get(path)
        assert await response.read() == b""

    assert "live stream cleanup failed: shutdown timed out" in caplog.text


@pytest.mark.parametrize(
    "path",
    [
        f"/api/ezviz/vtm/{SERIAL}.ts",
        f"/api/ezviz/vtm/{SERIAL}.ts?auth=wrong-token",
        f"/api/ezviz/vtm/{SERIAL}.ts?auth=%C5%BC%C3%B3%C5%82%C4%87",
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
    """Test the view rejects a missing or wrong token and an unknown serial."""
    await _setup_vtm_camera(hass, mock_config_entry, mock_ezviz_client)
    token = _token(await async_get_stream_source(hass, ENTITY_ID))
    client = await hass_client_no_auth()

    with patch(OPEN_STREAM) as mock_open:
        response = await client.get(path.format(token=token))

    assert response.status == 404
    mock_open.assert_not_called()


async def test_vtm_token_is_scoped_per_camera(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_ezviz_client: AsyncMock,
) -> None:
    """Test one camera's token cannot open another camera's stream."""
    mock_ezviz_client.load_cameras.return_value = {
        SERIAL: _mock_camera_data(reported_local_rtsp_port=0),
        "C987654321": _mock_camera_data(name="Camera 2", reported_local_rtsp_port=0),
    }
    await setup_integration(hass, mock_config_entry)
    path = _local_url(await async_get_stream_source(hass, ENTITY_ID))
    other = await async_get_stream_source(hass, "camera.camera_2")
    assert _token(path) != _token(other)
    client = await hass_client_no_auth()

    with patch(OPEN_STREAM) as mock_open:
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

    with patch(OPEN_STREAM) as mock_open:
        response = await client.get(path)

    assert response.status == 404
    mock_open.assert_not_called()


async def test_vtm_unload_ends_running_stream(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_ezviz_client: AsyncMock,
) -> None:
    """Test unloading the config entry ends and closes running streams."""
    await _setup_vtm_camera(hass, mock_config_entry, mock_ezviz_client)
    path = _local_url(await async_get_stream_source(hass, ENTITY_ID))
    client = await hass_client_no_auth()
    stream = FakeLiveStream([b"\x47first"], block=True)

    with patch(OPEN_STREAM, return_value=stream):
        request = asyncio.create_task(client.get(path))
        response = await request
        assert await response.content.readexactly(6) == b"\x47first"
        assert await hass.async_add_executor_job(stream.reading.wait, 10)
        camera = hass.data[DATA_VTM][SERIAL]
        assert camera.streams

        await hass.config_entries.async_unload(mock_config_entry.entry_id)
        with pytest.raises(ClientPayloadError):
            await response.read()

    assert await hass.async_add_executor_job(stream.closed.wait, 10)
    assert not camera.streams


async def test_vtm_unload_while_opening(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_ezviz_client: AsyncMock,
) -> None:
    """Test a stream still opening during unload is closed once it opens."""
    await _setup_vtm_camera(hass, mock_config_entry, mock_ezviz_client)
    path = _local_url(await async_get_stream_source(hass, ENTITY_ID))
    client = await hass_client_no_auth()
    opening = threading.Event()
    release = threading.Event()
    stream = FakeLiveStream()

    def _open(*_args: object, **_kwargs: object) -> FakeLiveStream:
        opening.set()
        release.wait(10)
        return stream

    # A plain function, not a Mock: the test harness runs Mock executor jobs
    # inline, which would block the event loop here.
    with patch(OPEN_STREAM, new=_open):
        request = asyncio.create_task(client.get(path))
        assert await hass.async_add_executor_job(opening.wait, 10)
        camera = hass.data[DATA_VTM][SERIAL]
        assert camera.streams

        await hass.config_entries.async_unload(mock_config_entry.entry_id)
        with pytest.raises(ClientError):
            await request
        release.set()
        assert await hass.async_add_executor_job(stream.closed.wait, 10)

    assert not camera.streams


async def test_vtm_camera_image_uses_last_alarm_picture(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_ezviz_client: AsyncMock,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test still images do not open a stream and wake the device."""
    aioclient_mock.get(ALARM_PIC_URL, content=b"alarm-jpeg")
    await _setup_vtm_camera(
        hass, mock_config_entry, mock_ezviz_client, last_alarm_pic=ALARM_PIC_URL
    )

    with patch(OPEN_STREAM) as mock_open:
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
            reported_local_rtsp_port=0,
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
