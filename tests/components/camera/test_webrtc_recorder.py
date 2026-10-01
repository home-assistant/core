"""Test camera WebRTC recording."""

import asyncio
from collections.abc import Awaitable, Callable, Generator
import concurrent.futures
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path
from typing import cast, override
from unittest.mock import AsyncMock, Mock, patch

from aiortc import (
    RTCIceCandidate,
    RTCRtpTransceiver,
    RTCSessionDescription,
    VideoStreamTrack,
)
from aiortc.mediastreams import MediaStreamError
from av import VideoFrame, open as av_open
import pytest

from homeassistant.components.camera import (
    Camera,
    WebRTCAnswer,
    WebRTCClientConfiguration,
    WebRTCRecordingConfiguration,
    WebRTCSendMessage,
)
from homeassistant.components.camera.webrtc_recorder import async_record_webrtc
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

VIDEO_SIZE = (200, 100)


class _VideoTrack(VideoStreamTrack):
    def __init__(self, on_frame_emitted: Callable[[], None]) -> None:
        super().__init__()
        self._loop = asyncio.get_running_loop()
        self._frame_semaphore = asyncio.Semaphore(0)
        self._stopped = asyncio.Event()
        self._on_frame_emitted = on_frame_emitted

    def emit_frame_threadsafe(self) -> None:
        self._loop.call_soon_threadsafe(self._frame_semaphore.release)

    def stop_threadsafe(self) -> None:
        self._loop.call_soon_threadsafe(self._stop)

    def _stop(self) -> None:
        self.stop()
        self._stopped.set()
        self._frame_semaphore.release()

    @override
    async def recv(self) -> VideoFrame:
        await self._frame_semaphore.acquire()
        if self._stopped.is_set():
            raise MediaStreamError
        pts, time_base = await self.next_timestamp()
        frame = VideoFrame(*VIDEO_SIZE, format="yuv420p")
        frame.pts = pts
        frame.time_base = time_base
        self._on_frame_emitted()
        return frame


@dataclass
class _RecordingContext:
    camera: Mock
    main_loop: asyncio.AbstractEventLoop
    video_track: concurrent.futures.Future[_VideoTrack] = field(
        default_factory=concurrent.futures.Future
    )
    frame_emitted: asyncio.Event = field(default_factory=asyncio.Event)
    peer_connection: _MockPeerConnection | None = None
    transceivers: dict[str, Mock] = field(default_factory=dict)

    def on_frame_emitted(self) -> None:
        self.main_loop.call_soon_threadsafe(self.frame_emitted.set)

    async def emit_video_frame(self) -> None:
        async with asyncio.timeout(1):
            track = await asyncio.shield(asyncio.wrap_future(self.video_track))
            self.frame_emitted.clear()
            track.emit_frame_threadsafe()
            await self.frame_emitted.wait()

    async def stop_video(self) -> None:
        async with asyncio.timeout(1):
            track = await asyncio.shield(asyncio.wrap_future(self.video_track))
            track.stop_threadsafe()


class _MockPeerConnection:
    def __init__(self, ctx: _RecordingContext, **_kwargs: object) -> None:
        self._ctx = ctx
        self._loop = asyncio.get_running_loop()
        self._callbacks: dict[str, Callable[..., object]] = {}
        self.connectionState = "new"
        self.localDescription: RTCSessionDescription | None = None
        self.remoteDescription: RTCSessionDescription | None = None
        ctx.peer_connection = self

    def on(self, event: str, callback: Callable[..., object]) -> Callable[..., object]:
        self._callbacks[event] = callback
        return callback

    def addTransceiver(self, kind: str, *, direction: str) -> Mock:
        transceiver = Mock(spec=RTCRtpTransceiver)
        self._ctx.transceivers[kind] = transceiver
        return transceiver

    def createDataChannel(self, _label: str) -> None:
        raise NotImplementedError

    async def createOffer(self) -> RTCSessionDescription:
        return RTCSessionDescription(sdp="v=0\r\n", type="offer")

    async def setLocalDescription(self, description: RTCSessionDescription) -> None:
        self.localDescription = description

    async def setRemoteDescription(self, description: RTCSessionDescription) -> None:
        self.remoteDescription = description
        track = _VideoTrack(self._ctx.on_frame_emitted)
        self._ctx.video_track.set_result(track)
        self._callbacks["track"](track)
        await self._set_connection_state("connected")

    async def addIceCandidate(self, _candidate: RTCIceCandidate | None) -> None:
        raise NotImplementedError

    async def close(self) -> None:
        await self._set_connection_state("closed")

    def fail_threadsafe(self) -> concurrent.futures.Future[None]:
        return asyncio.run_coroutine_threadsafe(
            self._set_connection_state("closed"), self._loop
        )

    async def _set_connection_state(self, state: str) -> None:
        self.connectionState = state
        await cast(Awaitable[None], self._callbacks["connectionstatechange"]())


@pytest.fixture
def recording_ctx(hass: HomeAssistant) -> Generator[_RecordingContext]:
    """Set up a camera with fake aiortc dependencies."""
    camera = Mock(spec=Camera)
    camera.hass = hass
    camera.entity_id = "camera.test"
    camera.async_get_webrtc_client_configuration.return_value = (
        WebRTCClientConfiguration()
    )
    camera.get_webrtc_recording_configuration.return_value = (
        WebRTCRecordingConfiguration()
    )

    async def handle_offer(
        offer_sdp: str,
        session_id: str,
        send_message: WebRTCSendMessage,
        *,
        aiortc_compatible: bool,
    ) -> None:
        assert offer_sdp == "v=0\r\n"
        assert session_id
        assert aiortc_compatible
        send_message(WebRTCAnswer(answer="v=0\r\n"))

    camera.async_handle_async_webrtc_offer = AsyncMock(side_effect=handle_offer)
    ctx = _RecordingContext(camera, hass.loop)

    with (
        patch.object(hass.config, "is_allowed_path", return_value=True),
        patch(
            "homeassistant.components.camera.webrtc_recorder.RTCPeerConnection",
            partial(_MockPeerConnection, ctx),
        ),
    ):
        yield ctx


def _get_video_frame_sizes(path: Path) -> list[tuple[int, int]]:
    with av_open(path) as container:
        return [(frame.width, frame.height) for frame in container.decode(video=0)]


async def test_record_success(tmp_path: Path, recording_ctx: _RecordingContext) -> None:
    """Test recording a WebRTC stream to a file."""
    output = tmp_path / "recording.mp4"
    recording_ctx.camera.get_webrtc_recording_configuration.return_value = (
        WebRTCRecordingConfiguration(
            audio_codec="audio/opus",
            video_codec="video/H264",
            video_codec_parameters={"profile-level-id": "42e01f"},
        )
    )

    task = asyncio.create_task(
        async_record_webrtc(recording_ctx.camera, str(output), 0.2)
    )
    await recording_ctx.emit_video_frame()
    await recording_ctx.emit_video_frame()
    await task

    assert _get_video_frame_sizes(output) == [VIDEO_SIZE] * 2

    audio_set_preferences = recording_ctx.transceivers["audio"].setCodecPreferences
    audio_set_preferences.assert_called_once()
    (audio_codecs,) = audio_set_preferences.call_args.args
    assert len(audio_codecs) == 1
    assert audio_codecs[0].mimeType == "audio/opus"

    video_set_preferences = recording_ctx.transceivers["video"].setCodecPreferences
    video_set_preferences.assert_called_once()
    (video_codecs,) = video_set_preferences.call_args.args
    assert len(video_codecs) == 1
    assert video_codecs[0].mimeType == "video/H264"
    assert video_codecs[0].parameters["profile-level-id"] == "42e01f"

    recording_ctx.camera.async_handle_async_webrtc_offer.assert_awaited_once()
    recording_ctx.camera.close_webrtc_session.assert_called_once()


async def test_record_cancellation(
    tmp_path: Path, recording_ctx: _RecordingContext
) -> None:
    """Test cancelling a recording stops and cleans up the worker."""
    output = tmp_path / "recording.mp4"
    task = asyncio.create_task(
        async_record_webrtc(recording_ctx.camera, str(output), 60)
    )
    await recording_ctx.emit_video_frame()
    await recording_ctx.emit_video_frame()

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert _get_video_frame_sizes(output) == [VIDEO_SIZE] * 2
    recording_ctx.camera.close_webrtc_session.assert_called_once()


async def test_record_video_track_stops(
    tmp_path: Path, recording_ctx: _RecordingContext
) -> None:
    """Test that recording succeeds when a VideoTrack stops producing frames."""
    output = tmp_path / "recording.mp4"
    task = asyncio.create_task(
        async_record_webrtc(recording_ctx.camera, str(output), 0.2)
    )
    await recording_ctx.emit_video_frame()
    await recording_ctx.emit_video_frame()
    await recording_ctx.stop_video()
    await task

    assert _get_video_frame_sizes(output) == [VIDEO_SIZE] * 2
    recording_ctx.camera.close_webrtc_session.assert_called_once()


async def test_record_connection_closes_prematurely(
    tmp_path: Path, recording_ctx: _RecordingContext
) -> None:
    """Test a connection closing prematurely fails and cleans up the recording."""
    output = tmp_path / "recording.mp4"
    task = asyncio.create_task(
        async_record_webrtc(recording_ctx.camera, str(output), 60)
    )
    await recording_ctx.emit_video_frame()
    await recording_ctx.emit_video_frame()
    peer_connection = recording_ctx.peer_connection
    assert peer_connection is not None

    await asyncio.wrap_future(peer_connection.fail_threadsafe())
    with pytest.raises(
        HomeAssistantError,
        match="WebRTC connection closed before recording finished",
    ):
        await task

    assert _get_video_frame_sizes(output) == [VIDEO_SIZE] * 2
    recording_ctx.camera.close_webrtc_session.assert_called_once()
