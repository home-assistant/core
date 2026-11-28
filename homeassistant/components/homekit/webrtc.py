"""Receive compressed camera WebRTC video for HomeKit's FFmpeg input.

Experimental adapter: aiortc's PyAV 19 requirement and packet-receive API must
be supported upstream before this adapter can become an installed dependency.
"""

import asyncio
from collections import deque
from collections.abc import Awaitable, Callable, Coroutine
from dataclasses import dataclass, field
from functools import cache
from io import BytesIO
import logging
import queue
import socket
import struct
from typing import TYPE_CHECKING, Any, override

from homeassistant.components.camera import Camera, CameraWebRTCSession
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

if TYPE_CHECKING:
    from aiortc import RTCPeerConnection
    from aiortc.rtcdtlstransport import RTCDtlsTransport

type RTPHandler = Callable[[bytes, int], Awaitable[None]]

MEDIA_TIMEOUT = 15

INPUT_SOURCE = (
    "-protocol_whitelist pipe,udp,rtp -f sdp "
    "-localaddr 127.0.0.1 "
    "-buffer_size 1048576 "
    "-fpsprobesize 0 -analyzeduration 15000000 -probesize 10000000 -i pipe:0"
)


class _SDPLogFilter(logging.Filter):
    """Drop dependency SDP dumps while retaining transport diagnostics."""

    @override
    def filter(self, record: logging.LogRecord) -> bool:
        return not str(record.msg).startswith(
            (
                "RTCPeerConnection() setLocalDescription(",
                "RTCPeerConnection() setRemoteDescription(",
            )
        )


@cache
def _protect_sdp_logs() -> None:
    """Install once before any aiortc signaling can expose credentials."""
    logging.getLogger("aiortc.rtcpeerconnection").addFilter(_SDPLogFilter())


def normalize_answer(answer: str) -> str:
    """Supply Nest's omitted candidate foundation without logging SDP."""
    lines = answer.splitlines()
    for index, line in enumerate(lines):
        if not line.startswith("a=candidate:"):
            continue
        value = line.removeprefix("a=candidate:")
        parts = value.split()
        if (
            len(parts) >= 7
            and parts[0] in ("1", "2")
            and parts[1].lower() in ("udp", "tcp")
            and parts[2].isdigit()
            and parts[4].isdigit()
            and parts[5] == "typ"
        ):
            value = "0 " + value.lstrip()
            parts = value.split()
            lines[index] = "a=candidate:" + value
        if (
            len(parts) < 8
            or not parts[1].isdigit()
            or not parts[3].isdigit()
            or not parts[5].isdigit()
            or parts[2].lower() not in ("udp", "tcp")
            or parts[6] != "typ"
        ):
            raise HomeAssistantError("Invalid camera ICE candidate")
    return "\r\n".join(lines) + "\r\n"


class _DiscardDecodeQueue(queue.Queue[object]):
    """Keep worker shutdown intact without allocating codec decoders."""

    @override
    def put(
        self, item: object, block: bool = True, timeout: float | None = None
    ) -> None:
        if item is None:
            super().put(item, block=block, timeout=timeout)


class _SnapshotDecodeQueue(queue.Queue[object]):
    """Decode video only while a HomeKit snapshot is being requested."""

    def __init__(self) -> None:
        super().__init__()
        self.enabled = False

    @override
    def put(
        self, item: object, block: bool = True, timeout: float | None = None
    ) -> None:
        if item is None or self.enabled:
            super().put(item, block=block, timeout=timeout)

    def enable(self) -> None:
        """Allow one encoded frame to reach aiortc's decoder worker."""
        self.enabled = True

    def disable(self) -> None:
        """Stop decoding and discard frames queued during shutdown."""
        self.enabled = False
        while not self.empty():
            try:
                self.get_nowait()
            except queue.Empty:
                break


@dataclass(slots=True)
class _Viewer:
    """Own one independent FFmpeg input fed by a shared source."""

    viewer_id: int
    port: int
    sender: socket.socket
    reservations: list[socket.socket] = field(default_factory=list)
    progress: asyncio.Task[None] | None = None
    output: asyncio.Event = field(default_factory=asyncio.Event)
    failed: bool = False
    on_failure: Callable[[], Coroutine[Any, Any, None]] | None = None


class WebRTCCameraSource:
    """Own one peer/session and fan out encoded RTP to independent viewers."""

    input_source = INPUT_SOURCE

    def __init__(self, hass: HomeAssistant, camera: Camera) -> None:
        """Prepare ownership before negotiation can be cancelled."""
        _protect_sdp_logs()
        self.hass = hass
        self.camera = camera
        self.sdp = b""
        self.on_failure: Callable[[], Coroutine[Any, Any, None]] | None = None
        self._peer: RTCPeerConnection | None = None
        self._upstream: CameraWebRTCSession | None = None
        self._sender: socket.socket | None = None
        self._reservations: list[socket.socket] = []
        self._port = 0
        self._payload_type = -1
        self._handlers: dict[RTCDtlsTransport, RTPHandler] = {}
        self._video_receiver: Any = None
        self._snapshot_decode_queue: _SnapshotDecodeQueue | None = None
        self._snapshot_lock = asyncio.Lock()
        self._pending: deque[bytes] = deque()
        self._pending_size = 0
        self._active = False
        self._closed = False
        self._failed = False
        self._media = asyncio.Event()
        self._feedback: asyncio.Task[None] | None = None
        self._progress: asyncio.Task[None] | None = None
        self._close_task: asyncio.Task[None] | None = None
        self._viewers: dict[int, _Viewer] = {}
        self._next_viewer_id = 0
        self._legacy_viewer_id: int | None = None

    @property
    def is_started(self) -> bool:
        """Return whether the upstream peer has been created."""
        return self._peer is not None

    @property
    def has_viewers(self) -> bool:
        """Return whether any HomeKit live viewer is attached."""
        return bool(self._viewers)

    @property
    def is_closed(self) -> bool:
        """Return whether source cleanup has begun."""
        return self._closed

    async def async_start(self) -> None:
        """Negotiate H.264 using credentials owned by the camera integration."""
        if self._closed:
            raise HomeAssistantError("Camera WebRTC stream is already closed")
        if self._peer is not None:
            raise HomeAssistantError("Camera WebRTC stream is already started")
        # The existing source path does not import this optional draft dependency.
        from aiortc import (  # noqa: PLC0415
            RTCConfiguration,
            RTCIceServer,
            RTCPeerConnection,
            RTCRtpSender,
            RTCSessionDescription,
        )
        from aiortc.exceptions import OperationError  # noqa: PLC0415
        from aiortc.sdp import SessionDescription  # noqa: PLC0415

        configuration = self.camera.async_get_webrtc_client_configuration()
        servers = [
            RTCIceServer(
                urls=server.urls,
                username=server.username,
                credential=server.credential,
            )
            for server in configuration.configuration.ice_servers
        ]
        peer = self._peer = RTCPeerConnection(RTCConfiguration(iceServers=servers))
        for kind in ("audio", "video"):
            transceiver = peer.addTransceiver(kind, direction="recvonly")
            codecs = RTCRtpSender.getCapabilities(kind).codecs
            if kind == "audio":
                codecs = [codec for codec in codecs if codec.mimeType == "audio/opus"]
            else:
                codecs = [
                    codec
                    for codec in codecs
                    if codec.mimeType == "video/H264"
                    and codec.parameters.get("profile-level-id") == "42e01f"
                ]
            if not codecs:
                raise HomeAssistantError("Required camera codec is unavailable")
            transceiver.setCodecPreferences(codecs)
            # Draft-only hook against the pinned/probed aiortc 1.15 receiver.
            receiver_state = transceiver.receiver.__dict__
            if "_RTCRtpReceiver__decoder_queue" not in receiver_state:
                raise HomeAssistantError("Unsupported WebRTC packet receiver API")
            if kind == "video":
                self._video_receiver = transceiver.receiver
                self._snapshot_decode_queue = _SnapshotDecodeQueue()
                receiver_state["_RTCRtpReceiver__decoder_queue"] = (
                    self._snapshot_decode_queue
                )
            else:
                receiver_state["_RTCRtpReceiver__decoder_queue"] = _DiscardDecodeQueue()
        if configuration.data_channel:
            peer.createDataChannel(configuration.data_channel, id=1)

        @peer.on("connectionstatechange")
        def connection_changed() -> None:
            if not self._closed and peer.connectionState in ("failed", "disconnected"):
                self._connection_failed()

        async with asyncio.timeout(30):
            offer = await peer.createOffer()
            await peer.setLocalDescription(offer)
            assert peer.localDescription is not None
            self._upstream = await self.camera.async_create_webrtc_session(
                peer.localDescription.sdp
            )
            answer = normalize_answer(self._upstream.answer)
            video = [
                codec
                for media in SessionDescription.parse(answer).media
                if media.kind == "video"
                for codec in media.rtp.codecs
                if codec.mimeType == "video/H264"
            ]
            if len(video) != 1 or video[0].parameters.get("packetization-mode") != "1":
                raise HomeAssistantError("Camera did not negotiate supported H.264")
            payload_type = video[0].payloadType
            if payload_type is None:
                raise HomeAssistantError("Camera video payload type is missing")
            self._payload_type = payload_type
            for transceiver in peer.getTransceivers():
                transport = transceiver.receiver.transport
                if transport in self._handlers:
                    continue
                original = transport._handle_rtp_data  # noqa: SLF001
                self._handlers[transport] = original

                async def receive(
                    data: bytes, arrival_time_ms: int, handler: RTPHandler = original
                ) -> None:
                    self._receive_packet(data)
                    await handler(data, arrival_time_ms)

                transport._handle_rtp_data = receive  # type: ignore[method-assign]  # noqa: SLF001
            try:
                await peer.setRemoteDescription(RTCSessionDescription(answer, "answer"))
            except OperationError:
                raise HomeAssistantError("Camera WebRTC negotiation failed") from None

    def _reserve_ports(self) -> None:
        """Hold an RTP/RTCP pair until FFmpeg is ready to consume local SDP."""
        for _ in range(20):
            rtp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            rtcp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                rtp.bind(("127.0.0.1", 0))
                port = rtp.getsockname()[1]
                if port == 65535:
                    rtp.close()
                    rtcp.close()
                    continue
                rtcp.bind(("127.0.0.1", port + 1))
            except OSError:
                rtp.close()
                rtcp.close()
                continue
            self._port = port
            self._reservations = [rtp, rtcp]
            return
        raise HomeAssistantError("Could not reserve local camera RTP ports")

    def _receive_packet(self, data: bytes) -> None:
        """Preserve RTP packets and fan them out without rewriting sequence data."""
        from aiortc.rtp import RtpPacket  # noqa: PLC0415

        if self._closed:
            return
        try:
            packet = RtpPacket.parse(data)
        except ValueError:
            return
        # Removing padding creates sequence gaps and stalls FFmpeg's reorder queue.
        if packet.payload_type != self._payload_type:
            return
        if self._viewers:
            for viewer in tuple(self._viewers.values()):
                try:
                    viewer.sender.sendto(data, ("127.0.0.1", viewer.port))
                except OSError:
                    self._viewer_failed(viewer)
            return
        if self._active:
            assert self._sender is not None
            try:
                self._sender.sendto(data, ("127.0.0.1", self._port))
            except OSError:
                self._connection_failed()
                return
        else:
            self._pending.append(data)
            self._pending_size += len(data)
            while self._pending_size > 512 * 1024:
                self._pending_size -= len(self._pending.popleft())

    def _reserve_viewer(self) -> tuple[int, list[socket.socket], socket.socket]:
        """Reserve one viewer's RTP socket until FFmpeg consumes its SDP."""
        for _ in range(20):
            rtp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            rtcp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                rtp.bind(("127.0.0.1", 0))
                port = rtp.getsockname()[1]
                if port == 65535:
                    rtp.close()
                    rtcp.close()
                    continue
                rtcp.bind(("127.0.0.1", port + 1))
            except OSError:
                rtp.close()
                rtcp.close()
                continue
            sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sender.setblocking(False)
            return port, [rtp, rtcp], sender
        raise HomeAssistantError("Could not reserve local camera RTP ports")

    async def async_add_viewer(
        self,
        writer: asyncio.StreamWriter,
        reader: asyncio.StreamReader,
        *,
        on_failure: Callable[[], Coroutine[Any, Any, None]] | None = None,
    ) -> int:
        """Start an independent local FFmpeg input for this HomeKit viewer."""
        if self._closed:
            raise HomeAssistantError("Camera WebRTC stream is closed")
        if self._payload_type < 0:
            raise HomeAssistantError("Camera WebRTC input is not ready")
        port, reservations, sender = self._reserve_viewer()
        viewer_id = self._next_viewer_id
        self._next_viewer_id += 1
        viewer = _Viewer(viewer_id, port, sender, reservations, on_failure=on_failure)
        self._viewers[viewer_id] = viewer
        try:
            for reserved in reservations:
                reserved.close()
            viewer.reservations.clear()
            sdp = (
                "v=0\r\no=- 0 0 IN IP4 127.0.0.1\r\ns=HomeKit camera\r\n"
                "c=IN IP4 127.0.0.1\r\nt=0 0\r\n"
                f"m=video {port} RTP/AVP {self._payload_type}\r\n"
                f"a=rtpmap:{self._payload_type} H264/90000\r\n"
                "a=fmtp:"
                f"{self._payload_type} packetization-mode=1;profile-level-id=42e01f\r\n"
                "a=recvonly\r\n"
            ).encode("ascii")
            writer.write(sdp)
            await writer.drain()
            writer.close()
            self._active = True
            for packet in self._pending:
                sender.sendto(packet, ("127.0.0.1", port))
            self._pending.clear()
            self._pending_size = 0
            viewer.progress = asyncio.create_task(
                self._async_watch_viewer_output(viewer, reader)
            )
            if self._feedback is None or self._feedback.done():
                self._feedback = asyncio.create_task(self._async_request_keyframes())
            async with asyncio.timeout(MEDIA_TIMEOUT):
                await viewer.output.wait()
        except TimeoutError:
            writer.close()
            await self.async_remove_viewer(viewer_id)
            raise HomeAssistantError("Camera WebRTC viewer produced no video") from None
        except BaseException:
            writer.close()
            await self.async_remove_viewer(viewer_id)
            raise
        if viewer.failed:
            writer.close()
            await self.async_remove_viewer(viewer_id)
            raise HomeAssistantError("Camera WebRTC viewer failed")
        return viewer_id

    def _viewer_failed(self, viewer: _Viewer) -> None:
        """Drop one broken viewer and notify its owning HomeKit session."""
        if viewer.failed or self._viewers.get(viewer.viewer_id) is not viewer:
            return
        viewer.failed = True
        viewer.output.set()

        async def remove_and_notify() -> None:
            await self.async_remove_viewer(viewer.viewer_id)
            if viewer.on_failure:
                await viewer.on_failure()

        self.hass.async_create_background_task(
            remove_and_notify(), "homekit-webrtc-viewer-failed"
        )

    async def _async_watch_viewer_output(
        self, viewer: _Viewer, reader: asyncio.StreamReader
    ) -> None:
        """Keep one viewer only while its FFmpeg output continues advancing."""
        loop = asyncio.get_running_loop()
        deadline = loop.time() + MEDIA_TIMEOUT
        frames = 0
        try:
            while not self._closed and viewer.viewer_id in self._viewers:
                async with asyncio.timeout_at(deadline):
                    line = await reader.readline()
                if not line:
                    break
                if not line.startswith(b"frame="):
                    continue
                try:
                    current = int(line.removeprefix(b"frame="))
                except ValueError:
                    continue
                if current > frames:
                    frames = current
                    deadline = loop.time() + MEDIA_TIMEOUT
                    viewer.output.set()
                    self._media.set()
        except (TimeoutError, OSError, ValueError):
            pass
        if not self._closed and viewer.viewer_id in self._viewers:
            self._viewer_failed(viewer)

    async def async_remove_viewer(self, viewer_id: int) -> None:
        """Release one viewer's output without affecting other viewers."""
        if (viewer := self._viewers.pop(viewer_id, None)) is None:
            return
        if (
            viewer.progress is not None
            and viewer.progress is not asyncio.current_task()
        ):
            viewer.progress.cancel()
            await asyncio.gather(viewer.progress, return_exceptions=True)
        viewer.sender.close()
        for reserved in viewer.reservations:
            reserved.close()
        self._active = bool(self._viewers)

    def _connection_failed(self) -> None:
        """Notify the media owner once, without exposing transport credentials."""
        if self._failed or self._closed:
            return
        self._failed = True
        self._media.set()
        if self.on_failure:
            self.hass.async_create_background_task(
                self.on_failure(), "homekit-webrtc-failed"
            )

    async def async_activate(
        self, writer: asyncio.StreamWriter, reader: asyncio.StreamReader
    ) -> None:
        """Compatibility wrapper for callers that own a single viewer."""
        viewer_id = await self.async_add_viewer(writer, reader)
        self._legacy_viewer_id = viewer_id
        viewer = self._viewers[viewer_id]
        self._progress = viewer.progress
        self._port = viewer.port
        self._sender = viewer.sender

    async def _async_watch_output(self, reader: asyncio.StreamReader) -> None:
        """Require advancing FFmpeg output both at startup and throughout playback."""
        loop = asyncio.get_running_loop()
        deadline = loop.time() + MEDIA_TIMEOUT
        frames = 0
        try:
            while not self._closed:
                async with asyncio.timeout_at(deadline):
                    line = await reader.readline()
                if not line:
                    break
                if not line.startswith(b"frame="):
                    continue
                try:
                    current = int(line.removeprefix(b"frame="))
                except ValueError:
                    continue
                if current > frames:
                    frames = current
                    deadline = loop.time() + MEDIA_TIMEOUT
                    self._media.set()
        except (TimeoutError, OSError, ValueError):
            pass
        self._connection_failed()

    async def _async_request_keyframes(self) -> None:
        """Request parameter sets and full keyframes during FFmpeg startup."""
        from aiortc.rtp import RTCP_PSFB_FIR, RtcpPsfbPacket  # noqa: PLC0415

        if self._peer is None:
            return
        for sequence in range(3):
            await asyncio.sleep(2)
            for transceiver in self._peer.getTransceivers():
                if transceiver.kind != "video":
                    continue
                for source in transceiver.receiver.getSynchronizationSources():
                    await transceiver.receiver._send_rtcp_pli(source.source)  # noqa: SLF001
                    await transceiver.receiver._send_rtcp(  # noqa: SLF001
                        RtcpPsfbPacket(
                            fmt=RTCP_PSFB_FIR,
                            ssrc=transceiver.sender._ssrc,  # noqa: SLF001
                            media_ssrc=0,
                            fci=struct.pack("!LB3x", source.source, sequence),
                        )
                    )

    async def async_get_snapshot(self) -> bytes:
        """Decode one frame from this live session as a JPEG snapshot."""
        if self._video_receiver is None or self._snapshot_decode_queue is None:
            raise HomeAssistantError("Camera WebRTC video is not available")
        if self._closed:
            raise HomeAssistantError("Camera WebRTC stream is closed")

        async with self._snapshot_lock:
            receiver = self._video_receiver
            track = receiver.track
            frame_queue = track._queue  # noqa: SLF001
            while not frame_queue.empty():
                try:
                    frame_queue.get_nowait()
                except asyncio.QueueEmpty:
                    break

            self._snapshot_decode_queue.enable()
            try:
                for source in receiver.getSynchronizationSources():
                    await receiver._send_rtcp_pli(source.source)  # noqa: SLF001
                async with asyncio.timeout(MEDIA_TIMEOUT):
                    while not (frame := await track.recv()).key_frame:
                        # The decoder may first emit a delta frame from its
                        # recovery buffer. Only a fresh keyframe can establish
                        # the full image after snapshot decoding was disabled.
                        continue
                image = frame.to_image()
                with BytesIO() as output:
                    image.save(output, format="JPEG")
                    return output.getvalue()
            finally:
                self._snapshot_decode_queue.disable()
                while not frame_queue.empty():
                    try:
                        frame_queue.get_nowait()
                    except asyncio.QueueEmpty:
                        break

    async def async_close(self) -> None:
        """Close every owned resource once, even after partial startup."""
        if self._close_task is None:
            self._close_task = asyncio.create_task(self._async_close())
        await asyncio.shield(self._close_task)

    async def _async_close(self) -> None:
        self._closed = True
        for viewer_id in tuple(self._viewers):
            await self.async_remove_viewer(viewer_id)
        tasks = [task for task in (self._feedback, self._progress) if task is not None]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        try:
            if self._peer is not None:
                await self._peer.close()
        finally:
            try:
                if self._upstream is not None:
                    await self._upstream.async_close()
            finally:
                if self._sender is not None:
                    self._sender.close()
                for reserved in self._reservations:
                    reserved.close()
                self._reservations.clear()
                self._pending.clear()
                self._handlers.clear()
                self._video_receiver = None
                self._snapshot_decode_queue = None


# Kept as an alias while HomeKit's streaming code moves to the shared owner.
WebRTCCameraStream = WebRTCCameraSource
