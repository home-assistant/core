"""Bounded H.264 RTP packetization for a shared Secure Video stream."""

import asyncio
import base64
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass
from io import BytesIO
import logging
import math
import secrets
import socket
import struct
import time
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from av.container import InputContainer

_LOGGER = logging.getLogger(__name__)

_MAX_MEDIA = 16 * 1024 * 1024
_RTP_CLOCK = 90_000
_NTP_EPOCH = 2_208_988_800


@dataclass(frozen=True, slots=True)
class AccessUnit:
    """One compressed H.264 access unit and its original timebase."""

    pts: float
    dts: float
    duration: float
    nalus: tuple[bytes, ...]


def avcc_configuration(extra: bytes) -> tuple[int, tuple[bytes, ...]]:
    """Parse AVC decoder configuration and retain SPS/PPS for IDR frames."""
    if len(extra) < 7 or extra[0] != 1:
        raise ValueError("Missing AVC configuration")
    length_size = (extra[4] & 3) + 1
    position = 6
    parameter_sets = []
    counts = [extra[5] & 31]
    for group in range(2):
        if group:
            if position >= len(extra):
                raise ValueError("Missing AVC picture parameter sets")
            counts.append(extra[position])
            position += 1
        for _ in range(counts[group]):
            if position + 2 > len(extra):
                raise ValueError("Truncated AVC configuration")
            size = int.from_bytes(extra[position : position + 2], "big")
            position += 2
            if not size or position + size > len(extra):
                raise ValueError("Invalid AVC parameter set")
            parameter_sets.append(extra[position : position + size])
            position += size
    if not counts[0] or not counts[1]:
        raise ValueError("Missing AVC parameter sets")
    return length_size, tuple(parameter_sets)


def avcc_nalus(data: bytes, length_size: int) -> tuple[bytes, ...]:
    """Validate and split one length-prefixed H.264 access unit."""
    if not 1 <= length_size <= 4:
        raise ValueError("Invalid AVC length size")
    nalus = []
    position = 0
    while position < len(data):
        if position + length_size > len(data):
            raise ValueError("Truncated AVC length")
        size = int.from_bytes(data[position : position + length_size], "big")
        position += length_size
        if not size or position + size > len(data):
            raise ValueError("Truncated AVC NAL unit")
        nalus.append(data[position : position + size])
        position += size
    if not nalus:
        raise ValueError("Empty H.264 access unit")
    return tuple(nalus)


def h264_payloads(nalus: tuple[bytes, ...], payload_limit: int) -> Iterator[bytes]:
    """Packetize H.264 NAL units as single-NAL or FU-A RTP payloads."""
    if payload_limit < 3:
        raise ValueError("RTP payload limit is too small")
    if (
        len(nalus) >= 2
        and nalus[0]
        and nalus[0][0] & 31 == 7
        and nalus[1]
        and nalus[1][0] & 31 == 8
        and max(len(nalus[0]), len(nalus[1])) <= 65535
        and 5 + len(nalus[0]) + len(nalus[1]) <= payload_limit
    ):
        indicator = (max(nalus[0][0] & 0x60, nalus[1][0] & 0x60)) | 24
        yield (
            bytes((indicator,))
            + len(nalus[0]).to_bytes(2, "big")
            + nalus[0]
            + len(nalus[1]).to_bytes(2, "big")
            + nalus[1]
        )
        nalus = nalus[2:]
    for nalu in nalus:
        if not nalu:
            raise ValueError("Empty NAL unit")
        if len(nalu) <= payload_limit:
            yield nalu
            continue
        indicator = (nalu[0] & 0xE0) | 28
        nal_type = nalu[0] & 0x1F
        size = payload_limit - 2
        data = nalu[1:]
        for offset in range(0, len(data), size):
            end = min(offset + size, len(data))
            header = (
                nal_type
                | (0x80 if offset == 0 else 0)
                | (0x40 if end == len(data) else 0)
            )
            yield bytes((indicator, header)) + data[offset:end]


def inspect_part(initialization: bytes, part: bytes) -> tuple[AccessUnit, ...]:
    """Demux one bounded fMP4 part without decoding video; run in an executor."""
    import av  # noqa: PLC0415

    if not part or len(initialization) + len(part) > _MAX_MEDIA:
        raise ValueError("Invalid or oversized media part")
    with av.open(BytesIO(initialization + part), format="mp4") as raw_container:
        container = cast("InputContainer", raw_container)
        if len(container.streams.video) != 1:
            raise ValueError("Expected exactly one video stream")
        video = container.streams.video[0]
        if video.codec_context.name != "h264":
            raise ValueError("Expected H.264")
        length_size, parameter_sets = avcc_configuration(
            video.codec_context.extradata or b""
        )
        units = []
        for packet in container.demux(video):
            if packet.pts is None or packet.dts is None or packet.time_base is None:
                continue
            nalus = avcc_nalus(bytes(packet), length_size)
            if any(nalu[0] & 31 == 5 for nalu in nalus):
                nalus = parameter_sets + nalus
            units.append(
                AccessUnit(
                    float(packet.pts * packet.time_base),
                    float(packet.dts * packet.time_base),
                    float((packet.duration or 0) * packet.time_base),
                    nalus,
                )
            )
        return tuple(units)


def rtcp_receiver_loss(packet: bytes, ssrc: int) -> tuple[int, int] | None:
    """Read loss counts for our SSRC from an authenticated compound RTCP packet."""
    offset = 0
    while offset + 4 <= len(packet):
        version = packet[offset] >> 6
        count = packet[offset] & 31
        kind = packet[offset + 1]
        size = (int.from_bytes(packet[offset + 2 : offset + 4], "big") + 1) * 4
        if version != 2 or size < 4 or offset + size > len(packet):
            raise ValueError("Invalid RTCP packet")
        block_start = offset + (8 if kind == 201 else 28 if kind == 200 else size)
        for index in range(count if kind in (200, 201) else 0):
            block = block_start + 24 * index
            if block + 24 > offset + size:
                raise ValueError("Truncated RTCP report")
            if int.from_bytes(packet[block : block + 4], "big") == ssrc:
                return packet[block + 4], int.from_bytes(
                    packet[block + 5 : block + 8], "big", signed=True
                )
        offset += size
    if offset != len(packet):
        raise ValueError("Truncated RTCP packet")
    return None


def rtp_header(ssrc: int, sequence: int, timestamp: int, marker: bool) -> bytes:
    """Build an RTP header with wrapping timestamp and sequence numbers."""
    return struct.pack(
        ">BBHII",
        0x80,
        99 | (0x80 if marker else 0),
        sequence & 0xFFFF,
        timestamp & 0xFFFFFFFF,
        ssrc,
    )


def rtcp_sender_report(
    ssrc: int, timestamp: int, sent_wall: float, packets: int, octets: int
) -> bytes:
    """Correlate an RTP timestamp with the wall clock of that same packet."""
    now = sent_wall + _NTP_EPOCH
    seconds = int(now)
    fraction = int((now - seconds) * 2**32)
    return struct.pack(
        ">BBHIIIIII",
        0x80,
        200,
        6,
        ssrc,
        seconds & 0xFFFFFFFF,
        fraction,
        timestamp,
        packets & 0xFFFFFFFF,
        octets & 0xFFFFFFFF,
    )


class NativeVideoSender:
    """Packetize, pace and protect H.264 before transmitting UDP."""

    def __init__(
        self,
        key_b64: str,
        ssrc: int,
        address: str,
        port: int,
        mtu: int,
        initial_burst: float,
        local_port: int | None = None,
        rtcp_interval: float = 5.0,
    ) -> None:
        """Create isolated SRTP contexts for the HomeKit video session."""
        import pylibsrtp  # noqa: PLC0415

        key = base64.b64decode(key_b64, validate=True)
        if (
            len(key) != 30
            or mtu < 64
            or not 0 <= ssrc <= 0xFFFFFFFF
            or not math.isfinite(rtcp_interval)
            or rtcp_interval <= 0
        ):
            raise ValueError("Invalid SRTP parameters")
        self._send_crypto = pylibsrtp.Session(
            pylibsrtp.Policy(
                key=key, ssrc_type=pylibsrtp.Policy.SSRC_SPECIFIC, ssrc_value=ssrc
            )
        )
        self._receive_crypto = pylibsrtp.Session(
            pylibsrtp.Policy(key=key, ssrc_type=pylibsrtp.Policy.SSRC_ANY_INBOUND)
        )
        self._crypto_error = pylibsrtp.Error
        self._ssrc = ssrc
        self._address = address
        self._port = port
        self._local_port = port if local_port is None else local_port
        self._rtcp_interval = max(0.5, rtcp_interval)
        self._payload_limit = min(mtu, 1350) - 12 - 10
        self._burst = max(0.0, initial_burst)
        self._sequence = secrets.randbits(16)
        self._timestamp = secrets.randbits(32)
        self._socket: socket.socket | None = None
        self._closed = False
        self._packets = 0
        self._frames = 0
        self._octets = 0
        self._last_rtp_timestamp = self._timestamp
        self._last_sent_wall: float | None = None
        self.authenticated_rtcp = 0
        self.rtcp_fraction_lost: int | None = None
        self.rtcp_cumulative_lost: int | None = None

    async def _receive_reports(self) -> None:
        assert self._socket is not None
        loop = asyncio.get_running_loop()
        while not self._closed:
            packet, peer = await loop.sock_recvfrom(self._socket, 2048)
            if peer[0] != self._address or peer[1] != self._port:
                continue
            try:
                report = self._receive_crypto.unprotect_rtcp(packet)
                loss = rtcp_receiver_loss(report, self._ssrc)
            except self._crypto_error, ValueError:
                continue
            self.authenticated_rtcp += 1
            if loss is not None:
                self.rtcp_fraction_lost, self.rtcp_cumulative_lost = loss

    async def _sender_reports(self) -> None:
        assert self._socket is not None
        loop = asyncio.get_running_loop()
        while not self._closed:
            await asyncio.sleep(self._rtcp_interval)
            if self._last_sent_wall is None:
                continue
            report = rtcp_sender_report(
                self._ssrc,
                self._last_rtp_timestamp,
                self._last_sent_wall,
                self._packets,
                self._octets,
            )
            await loop.sock_sendto(
                self._socket,
                self._send_crypto.protect_rtcp(report),
                (self._address, self._port),
            )

    async def run(self, source: AsyncIterator[bytes]) -> None:
        """Send a shared initialization and parts without buffering media indefinitely."""
        loop = asyncio.get_running_loop()
        family = socket.AF_INET6 if ":" in self._address else socket.AF_INET
        sock = socket.socket(family, socket.SOCK_DGRAM)
        sock.setblocking(False)
        try:
            sock.bind(
                ("::" if family == socket.AF_INET6 else "0.0.0.0", self._local_port)
            )
        except BaseException:
            sock.close()
            raise
        self._socket = sock
        receiver = asyncio.create_task(self._receive_reports())
        reports = asyncio.create_task(self._sender_reports())
        initialization = None
        first_dts = None
        start = loop.time() - self._burst
        last_dts = None
        last_send = loop.time()
        started_idr = False
        try:
            async for data in source:
                if initialization is None:
                    initialization = data
                    continue
                units = await asyncio.to_thread(inspect_part, initialization, data)
                for unit in units:
                    if last_dts is not None and unit.dts <= last_dts:
                        raise ValueError("Nonmonotonic source DTS")
                    if not started_idr:
                        if not any(nalu[0] & 31 == 5 for nalu in unit.nalus):
                            raise ValueError("Live video does not start with an IDR")
                        started_idr = True
                    if first_dts is None:
                        first_dts = unit.dts
                    frame_duration = unit.duration or (
                        unit.dts - last_dts if last_dts is not None else 1 / 30
                    )
                    last_dts = unit.dts
                    payloads = tuple(h264_payloads(unit.nalus, self._payload_limit))
                    if sum(map(len, payloads)) > _MAX_MEDIA:
                        raise ValueError("Oversized H.264 access unit")
                    rtp_timestamp = (
                        self._timestamp + round((unit.pts - first_dts) * _RTP_CLOCK)
                    ) & 0xFFFFFFFF
                    target = max(start + unit.dts - first_dts, last_send, loop.time())
                    interval = min(0.05, max(0.001, frame_duration * 0.8)) / max(
                        len(payloads), 1
                    )
                    for index, payload in enumerate(payloads):
                        if index % 8 == 0:
                            delay = target + index * interval - loop.time()
                            if delay > 0:
                                await asyncio.sleep(delay)
                        header = rtp_header(
                            self._ssrc,
                            self._sequence,
                            rtp_timestamp,
                            index == len(payloads) - 1,
                        )
                        encrypted = self._send_crypto.protect(header + payload)
                        await loop.sock_sendto(
                            sock, encrypted, (self._address, self._port)
                        )
                        self._sequence = (self._sequence + 1) & 0xFFFF
                        self._packets += 1
                        self._octets += len(payload)
                        self._last_rtp_timestamp = rtp_timestamp
                        self._last_sent_wall = time.time()
                    self._frames += 1
                    last_send = target + len(payloads) * interval
        finally:
            self._closed = True
            receiver.cancel()
            reports.cancel()
            await asyncio.gather(receiver, reports, return_exceptions=True)
            sock.close()
            self._socket = None
            _LOGGER.info(
                "Native live session ended frames=%s packets=%s authenticated_rtcp=%s fraction_lost=%s cumulative_lost=%s",
                self._frames,
                self._packets,
                self.authenticated_rtcp,
                self.rtcp_fraction_lost,
                self.rtcp_cumulative_lost,
            )
