"""Test camera WebRTC recording."""

from abc import abstractmethod
import asyncio
from collections.abc import Awaitable, Callable, Generator
import concurrent.futures
from dataclasses import dataclass, field, replace
from fractions import Fraction
from functools import partial
from pathlib import Path
from typing import cast, override
from unittest.mock import AsyncMock, Mock, patch

from aiortc import (
    MediaStreamTrack,
    RTCIceCandidate,
    RTCRtpTransceiver,
    RTCSessionDescription,
)
from aiortc.mediastreams import MediaStreamError
from av import AudioFrame, VideoFrame, open as av_open
import pytest
import webrtc_models

from homeassistant.components.camera import (
    Camera,
    WebRTCAnswer,
    WebRTCCandidate,
    WebRTCClientConfiguration,
    WebRTCMessage,
    WebRTCRecordingConfiguration,
    WebRTCSendMessage,
)
from homeassistant.components.camera.webrtc_recorder import async_record_webrtc
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util.async_ import run_callback_threadsafe

VIDEO_SIZE = (200, 100)
ICE_CANDIDATE_SDP = "1 1 udp 2122260223 192.0.2.1 12345 typ host"
AUDIO_SAMPLE_RATE = 48000
AUDIO_SAMPLES = 960


class _FrameTrack(MediaStreamTrack):
    def __init__(self, on_frame_emitted: Callable[[], None] | None = None) -> None:
        super().__init__()
        self._loop = asyncio.get_running_loop()
        self._frame_semaphore = asyncio.Semaphore(0)
        self._stopped = asyncio.Event()
        self._on_frame_emitted = on_frame_emitted
        self._frame_index = 0

    def emit_frame_threadsafe(self) -> concurrent.futures.Future[None]:
        return run_callback_threadsafe(self._loop, self._frame_semaphore.release)

    def stop_threadsafe(self) -> None:
        self._loop.call_soon_threadsafe(self._stop)

    def _stop(self) -> None:
        self.stop()
        self._stopped.set()
        self._frame_semaphore.release()

    @override
    async def recv(self) -> AudioFrame | VideoFrame:
        await self._frame_semaphore.acquire()
        if self._stopped.is_set():
            raise MediaStreamError
        frame = self._create_frame(self._frame_index)
        self._frame_index += 1
        if self._on_frame_emitted is not None:
            self._on_frame_emitted()
        return frame

    @abstractmethod
    def _create_frame(self, frame_index: int) -> AudioFrame | VideoFrame:
        """Create a frame with a timestamp."""


class _VideoTrack(_FrameTrack):
    kind = "video"

    @override
    def _create_frame(self, frame_index: int) -> VideoFrame:
        frame = VideoFrame(*VIDEO_SIZE, format="yuv420p")
        frame.pts = frame_index
        frame.time_base = Fraction(1, 30)
        return frame


class _AudioTrack(_FrameTrack):
    kind = "audio"

    @override
    def _create_frame(self, frame_index: int) -> AudioFrame:
        frame = AudioFrame(format="s16", layout="mono", samples=AUDIO_SAMPLES)
        frame.sample_rate = AUDIO_SAMPLE_RATE
        frame.pts = frame_index * AUDIO_SAMPLES
        frame.time_base = Fraction(1, AUDIO_SAMPLE_RATE)
        for plane in frame.planes:
            plane.update(bytes(plane.buffer_size))
        return frame


@dataclass
class _RecordingContext:
    camera: Mock
    main_loop: asyncio.AbstractEventLoop
    video_track: concurrent.futures.Future[_VideoTrack] = field(
        default_factory=concurrent.futures.Future
    )
    audio_track: concurrent.futures.Future[_AudioTrack] = field(
        default_factory=concurrent.futures.Future
    )
    video_frame_emitted: asyncio.Event = field(default_factory=asyncio.Event)
    messages: list[WebRTCMessage] = field(
        default_factory=lambda: [WebRTCAnswer(answer="v=0\r\n")]
    )
    peer_connection: _MockPeerConnection | None = None
    transceivers: dict[str, Mock] = field(default_factory=dict)

    def on_video_frame_emitted(self) -> None:
        self.main_loop.call_soon_threadsafe(self.video_frame_emitted.set)

    async def emit_audio_frame(self) -> None:
        """Queue audio without waiting for the video gate to open."""
        async with asyncio.timeout(1):
            track = await asyncio.shield(asyncio.wrap_future(self.audio_track))
            await asyncio.wrap_future(track.emit_frame_threadsafe())

    async def emit_video_frame(self) -> None:
        """Wait until the video track produces the requested frame."""
        async with asyncio.timeout(1):
            self.video_frame_emitted.clear()
            track = await asyncio.shield(asyncio.wrap_future(self.video_track))
            await asyncio.wrap_future(track.emit_frame_threadsafe())
            await self.video_frame_emitted.wait()

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
        self.ice_candidates: list[RTCIceCandidate | None] = []
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
        video_track = _VideoTrack(self._ctx.on_video_frame_emitted)
        audio_track = _AudioTrack()
        self._ctx.video_track.set_result(video_track)
        self._ctx.audio_track.set_result(audio_track)
        for track in (video_track, audio_track):
            self._callbacks["track"](track)
        await self._set_connection_state("connected")

    async def addIceCandidate(self, candidate: RTCIceCandidate | None) -> None:
        assert self.remoteDescription is not None
        self.ice_candidates.append(candidate)

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
    ctx = _RecordingContext(camera, hass.loop)

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
        for message in ctx.messages:
            send_message(message)

    camera.async_handle_async_webrtc_offer = AsyncMock(side_effect=handle_offer)

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


async def test_record_ice_candidates(
    tmp_path: Path, recording_ctx: _RecordingContext
) -> None:
    """Test camera ICE candidates are added after the remote description is set."""
    recording_ctx.messages = [
        WebRTCCandidate(
            webrtc_models.RTCIceCandidateInit(
                f"candidate:{ICE_CANDIDATE_SDP}",
                sdp_mid="1",
                sdp_m_line_index=1,
            )
        ),
        WebRTCAnswer(answer="v=0\r\n"),
        WebRTCCandidate(webrtc_models.RTCIceCandidate(ICE_CANDIDATE_SDP)),
        WebRTCCandidate(webrtc_models.RTCIceCandidateInit("")),
    ]
    task = asyncio.create_task(
        async_record_webrtc(recording_ctx.camera, str(tmp_path / "recording.mp4"), 0.2)
    )
    await recording_ctx.emit_video_frame()
    await recording_ctx.emit_video_frame()
    await task

    peer_connection = recording_ctx.peer_connection
    assert peer_connection is not None
    candidate = RTCIceCandidate(
        component=1,
        foundation="1",
        ip="192.0.2.1",
        port=12345,
        priority=2122260223,
        protocol="udp",
        type="host",
    )
    assert peer_connection.ice_candidates == [
        replace(candidate, sdpMid="1", sdpMLineIndex=1),
        candidate,
        None,
    ]


async def test_record_audio_before_video(
    tmp_path: Path, recording_ctx: _RecordingContext
) -> None:
    """Test audio arriving first does not corrupt the video dimensions."""
    output = tmp_path / "recording.mp4"
    task = asyncio.create_task(
        async_record_webrtc(recording_ctx.camera, str(output), 0.2)
    )
    for _ in range(4):
        await recording_ctx.emit_audio_frame()
    await recording_ctx.emit_video_frame()
    await recording_ctx.emit_video_frame()
    await task

    assert _get_video_frame_sizes(output) == [VIDEO_SIZE] * 2
    with av_open(output) as container:
        # Ensure the gate releases audio instead of silently dropping it.
        assert list(container.decode(audio=0))


async def test_record_video_before_audio(
    tmp_path: Path, recording_ctx: _RecordingContext
) -> None:
    """Test video arriving first preserves dimensions and records audio."""
    output = tmp_path / "recording.mp4"
    task = asyncio.create_task(
        async_record_webrtc(recording_ctx.camera, str(output), 0.2)
    )
    await recording_ctx.emit_video_frame()
    await recording_ctx.emit_video_frame()
    for _ in range(4):
        await recording_ctx.emit_audio_frame()
    await task

    assert _get_video_frame_sizes(output) == [VIDEO_SIZE] * 2
    with av_open(output) as container:
        # Ensure the gate releases audio instead of silently dropping it.
        assert list(container.decode(audio=0))


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
