"""Test the compressed camera input used by HomeKit."""

import asyncio
from collections.abc import AsyncGenerator
import logging
from unittest.mock import AsyncMock, MagicMock, PropertyMock, call, patch

import aiortc
from aiortc import RTCConfiguration, RTCPeerConnection, RTCSessionDescription
from aiortc.exceptions import OperationError
from aiortc.rtp import RtpPacket
from aiortc.sdp import SessionDescription
import pytest

from homeassistant.components.camera import Camera, WebRTCClientConfiguration
from homeassistant.components.homekit.webrtc import WebRTCCameraStream, normalize_answer
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError


@pytest.fixture
async def native_stream(
    hass: HomeAssistant,
) -> AsyncGenerator[tuple[WebRTCCameraStream, list[RTCSessionDescription]]]:
    """Exercise a real offer and receiver setup while mocking network edges."""
    camera = MagicMock(spec=Camera)
    camera.async_get_webrtc_client_configuration.return_value = (
        WebRTCClientConfiguration(data_channel="dataSendChannel")
    )
    upstream = MagicMock(async_close=AsyncMock())
    upstream.answer = (
        "v=0\r\no=- 0 0 IN IP4 192.0.2.1\r\ns=-\r\nt=0 0\r\n"
        "m=video 9 UDP/TLS/RTP/SAVPF 101\r\n"
        "a=rtpmap:101 H264/90000\r\n"
        "a=fmtp:101 packetization-mode=1;profile-level-id=42e01f\r\n"
        "a=ice-pwd:private-answer-password\r\n"
        "a=candidate: 1 udp 12345 192.0.2.1 5000 typ host generation 0\r\n"
    )
    camera.async_create_webrtc_session.return_value = upstream
    stream = WebRTCCameraStream(hass, camera)
    peer = RTCPeerConnection(RTCConfiguration(iceServers=[]))
    offers: list[RTCSessionDescription] = []

    async def remember_offer(offer: RTCSessionDescription) -> None:
        offers.append(offer)

    def reserve() -> None:
        stream._port = 50000

    with (
        patch("aiortc.RTCPeerConnection", return_value=peer),
        patch.object(peer, "setLocalDescription", side_effect=remember_offer),
        patch.object(peer, "setRemoteDescription", new_callable=AsyncMock),
        patch.object(
            type(peer),
            "localDescription",
            new_callable=PropertyMock,
            side_effect=lambda: offers[0],
        ),
        patch.object(stream, "_reserve_ports", side_effect=reserve),
        patch("homeassistant.components.homekit.webrtc.socket.socket"),
    ):
        try:
            yield stream, offers
        finally:
            await stream.async_close()


async def test_native_offer_and_local_media_input(
    native_stream: tuple[WebRTCCameraStream, list[RTCSessionDescription]],
) -> None:
    """Real codec negotiation builds a credential-free, payload-matched input."""
    stream, offers = native_stream
    await stream.async_start()
    offer = SessionDescription.parse(offers[0].sdp)
    assert [media.kind for media in offer.media] == ["audio", "video", "application"]
    assert [codec.mimeType for codec in offer.media[0].rtp.codecs] == ["audio/opus"]
    assert [codec.mimeType for codec in offer.media[1].rtp.codecs] == ["video/H264"]
    local = SessionDescription.parse(stream.sdp.decode()).media[0]
    assert local.rtp.codecs[0].payloadType == 101
    assert local.port == 50000
    assert b"private-answer-password" not in stream.sdp
    assert b"ice-pwd" not in stream.sdp
    stream.camera.async_create_webrtc_session.assert_awaited_once_with(offers[0].sdp)


async def test_unsupported_codec_releases_upstream(
    native_stream: tuple[WebRTCCameraStream, list[RTCSessionDescription]],
) -> None:
    """An unusable answer is rejected before the media input starts."""
    stream, _ = native_stream
    upstream = stream.camera.async_create_webrtc_session.return_value
    upstream.answer = "v=0\r\ns=-\r\nt=0 0\r\nm=video 9 UDP/TLS/RTP/SAVPF 96\r\na=rtpmap:96 VP8/90000\r\n"
    with pytest.raises(HomeAssistantError, match="supported H.264"):
        await stream.async_start()
    await stream.async_close()
    upstream.async_close.assert_awaited_once()


def test_missing_candidate_foundation() -> None:
    """Recognize Nest's omitted foundation without changing valid candidates."""
    candidate = "1 udp 12345 192.0.2.1 5000 typ host generation 0"
    assert (
        normalize_answer(f"a=candidate: {candidate}\r\n")
        == f"a=candidate:0 {candidate}\r\n"
    )
    valid = "a=candidate:abc 1 udp 12345 192.0.2.1 5000 typ host\r\n"
    assert normalize_answer(valid) == valid


@pytest.mark.parametrize("candidate", ["broken", "abc udp 123 192.0.2.1 5000 typ host"])
def test_invalid_answer_candidate(candidate: str) -> None:
    """Invalid candidates fail without exposing their contents."""
    with pytest.raises(HomeAssistantError, match="Invalid camera ICE candidate"):
        normalize_answer(f"a=candidate:{candidate}\r\n")


async def test_stream_close_is_idempotent(hass: HomeAssistant) -> None:
    """Every upstream and local resource has one cleanup owner."""
    camera = MagicMock()
    stream = WebRTCCameraStream(hass, camera)
    stream._peer = MagicMock(close=AsyncMock())
    peer = stream._peer
    stream._upstream = MagicMock(async_close=AsyncMock())
    upstream = stream._upstream
    stream._sender = MagicMock()
    sender = stream._sender
    await stream.async_close()
    await stream.async_close()
    peer.close.assert_awaited_once()
    upstream.async_close.assert_awaited_once()
    sender.close.assert_called_once()


async def test_cloud_close_runs_after_peer_close_failure(hass: HomeAssistant) -> None:
    """A failed peer teardown must still stop the cloud stream and sockets."""
    stream = WebRTCCameraStream(hass, MagicMock())
    stream._peer = MagicMock(close=AsyncMock(side_effect=RuntimeError("peer failed")))
    stream._upstream = MagicMock(async_close=AsyncMock())
    upstream = stream._upstream
    stream._sender = MagicMock()
    sender = stream._sender
    with pytest.raises(RuntimeError, match="peer failed"):
        await stream.async_close()
    upstream.async_close.assert_awaited_once()
    sender.close.assert_called_once()


def test_reserved_invalid_port_is_closed(hass: HomeAssistant) -> None:
    """An unusable RTP port must not leak the candidate socket pair."""
    stream = WebRTCCameraStream(hass, MagicMock())
    sockets = [MagicMock() for _ in range(4)]
    sockets[0].getsockname.return_value = ("127.0.0.1", 65535)
    sockets[2].getsockname.return_value = ("127.0.0.1", 50000)
    with patch(
        "homeassistant.components.homekit.webrtc.socket.socket", side_effect=sockets
    ):
        stream._reserve_ports()
    sockets[0].close.assert_called_once()
    sockets[1].close.assert_called_once()
    assert stream._port == 50000
    for sock in stream._reservations:
        sock.close()


async def test_closed_stream_cannot_restart(hass: HomeAssistant) -> None:
    """A shutdown racing startup cannot create another upstream peer."""
    stream = WebRTCCameraStream(hass, MagicMock())
    await stream.async_close()
    with pytest.raises(HomeAssistantError, match="already closed"):
        await stream.async_start()


async def test_packet_passthrough_and_padding(hass: HomeAssistant) -> None:
    """Padding preserves sequence continuity without hiding real gaps or reordering."""
    stream = WebRTCCameraStream(hass, MagicMock())
    stream._active = True
    stream._payload_type = 101
    stream._port = 50000
    stream._sender = MagicMock()
    sender = stream._sender
    payload = RtpPacket(
        payload_type=101,
        sequence_number=65535,
        timestamp=3000,
        ssrc=1,
        payload=b"\x65\x00",
    ).serialize()
    padding = RtpPacket(payload_type=101, sequence_number=0, timestamp=3000, ssrc=1)
    padding.padding_size = 1
    padded = padding.serialize()
    next_payload = RtpPacket(
        payload_type=101, sequence_number=3, timestamp=6000, ssrc=1, payload=b"\x41\x00"
    ).serialize()
    for data in (payload, padded, next_payload, payload):
        stream._receive_packet(data)
    stream._receive_packet(RtpPacket(payload_type=96, payload=b"audio").serialize())
    stream._receive_packet(b"invalid")
    assert sender.sendto.call_args_list == [
        call(payload, ("127.0.0.1", 50000)),
        call(padded, ("127.0.0.1", 50000)),
        call(next_payload, ("127.0.0.1", 50000)),
        call(payload, ("127.0.0.1", 50000)),
    ]
    assert not stream._media.is_set()
    await stream.async_close()


async def test_startup_buffer_preserves_padding(hass: HomeAssistant) -> None:
    """Startup buffering retains padding so activation cannot introduce sequence gaps."""
    stream = WebRTCCameraStream(hass, MagicMock())
    stream._payload_type = 101
    payload = RtpPacket(
        payload_type=101, sequence_number=10, payload=b"\x65"
    ).serialize()
    padding = RtpPacket(payload_type=101, sequence_number=11)
    padding.padding_size = 1
    padded = padding.serialize()
    stream._receive_packet(payload)
    stream._receive_packet(padded)
    assert list(stream._pending) == [payload, padded]
    assert stream._pending_size == len(payload) + len(padded)
    await stream.async_close()


async def test_startup_buffer_is_bounded(hass: HomeAssistant) -> None:
    """Negotiation cannot accumulate unlimited video while FFmpeg starts."""
    stream = WebRTCCameraStream(hass, MagicMock())
    stream._payload_type = 101
    payload = RtpPacket(
        payload_type=101,
        sequence_number=1,
        timestamp=3000,
        ssrc=1,
        payload=b"\x65" + bytes(1200),
    ).serialize()
    for _ in range(1000):
        stream._receive_packet(payload)
    assert 0 < stream._pending_size <= 512 * 1024
    await stream.async_close()
    assert not stream._pending


async def test_local_send_error_fails_session(hass: HomeAssistant) -> None:
    """A broken local media path reports failure rather than staying black."""
    stream = WebRTCCameraStream(hass, MagicMock())
    stream._active = True
    stream._payload_type = 101
    stream._sender = MagicMock()
    stream._sender.sendto.side_effect = OSError("local UDP failure")
    stream.on_failure = AsyncMock()
    packet = RtpPacket(payload_type=101, ssrc=1, payload=b"\x65\x00").serialize()
    stream._receive_packet(packet)
    await hass.async_block_till_done()
    stream.on_failure.assert_awaited_once()
    assert stream._failed
    await stream.async_close()


async def test_udp_send_does_not_prove_output(hass: HomeAssistant) -> None:
    """Local UDP acceptance is not evidence of FFmpeg output."""
    stream = WebRTCCameraStream(hass, MagicMock())
    stream._active = True
    stream._payload_type = 101
    stream._sender = MagicMock()
    stream._receive_packet(RtpPacket(payload_type=101, payload=b"\x65").serialize())
    assert not stream._media.is_set()
    await stream.async_close()


async def test_progress_stall_fails_stream(hass: HomeAssistant) -> None:
    """Actual output starts the session; subsequent silence fails it."""
    stream = WebRTCCameraStream(hass, MagicMock())
    stream.on_failure = AsyncMock()
    reader = asyncio.StreamReader()
    reader.feed_data(b"frame=1\nprogress=continue\n")
    with patch("homeassistant.components.homekit.webrtc.MEDIA_TIMEOUT", 0.01):
        task = asyncio.create_task(stream._async_watch_output(reader))
        await stream._media.wait()
        assert not stream._failed
        await task
        await hass.async_block_till_done()
    stream.on_failure.assert_awaited_once()
    assert stream._failed
    await stream.async_close()


async def test_no_output_fails_startup(hass: HomeAssistant) -> None:
    """Repeated zero-frame progress cannot postpone startup indefinitely."""
    stream = WebRTCCameraStream(hass, MagicMock())
    reader = asyncio.StreamReader()
    reader.feed_data(b"frame=0\nprogress=continue\n")
    with patch("homeassistant.components.homekit.webrtc.MEDIA_TIMEOUT", 0.01):
        await stream._async_watch_output(reader)
    assert stream._failed
    await stream.async_close()


def test_dependency_sdp_logging_is_redacted(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """The dependency logger cannot expose local or remote ICE secrets."""
    WebRTCCameraStream(hass, MagicMock())
    logger = logging.getLogger("aiortc.rtcpeerconnection")
    with caplog.at_level(logging.DEBUG, logger=logger.name):
        peer = RTCPeerConnection()
        peer._RTCPeerConnection__log_debug(
            "setRemoteDescription(%s)\n%s", "answer", "a=ice-pwd:secret-password"
        )
        peer._RTCPeerConnection__log_debug(
            "setLocalDescription(%s)\n%s", "offer", "a=ice-pwd:secret-password"
        )
        peer._RTCPeerConnection__log_debug("connectionState %s -> %s", "new", "closed")
    assert "secret-password" not in caplog.text
    assert "connectionState new -> closed" in caplog.text


async def test_negotiation_error_is_safe(
    native_stream: tuple[WebRTCCameraStream, list[RTCSessionDescription]],
) -> None:
    """Expected codec rejection follows the normal unsuccessful-start path."""
    stream, _ = native_stream
    with (
        patch.object(
            aiortc.RTCPeerConnection.return_value,
            "setRemoteDescription",
            side_effect=OperationError("secret-answer-content"),
        ),
        pytest.raises(HomeAssistantError, match="negotiation failed") as error,
    ):
        await stream.async_start()
    assert "secret-answer-content" not in str(error.value)


async def test_activate_requires_ffmpeg_output(hass: HomeAssistant) -> None:
    """The SDP handoff waits for output evidence and owns its progress watcher."""
    stream = WebRTCCameraStream(hass, MagicMock())
    reader = asyncio.StreamReader()
    writer = MagicMock(drain=AsyncMock())
    reader.feed_data(b"frame=1\nprogress=continue\n")
    with patch.object(stream, "_async_request_keyframes", new_callable=AsyncMock):
        await stream.async_activate(writer, reader)
        assert stream._media.is_set()
        assert not stream._failed
        await stream.async_close()
    assert stream._progress.done()
    writer.write.assert_called_once_with(stream.sdp)
    writer.close.assert_called_once()
