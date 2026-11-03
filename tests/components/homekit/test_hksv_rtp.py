"""Tests for native H.264 RTP packetization and SRTP."""

import asyncio
import base64
import struct
from unittest.mock import AsyncMock

import pytest

from homeassistant.components.homekit import hksv_rtp
from homeassistant.components.homekit.hksv_rtp import (
    NativeVideoSender,
    avcc_configuration,
    avcc_nalus,
    h264_payloads,
    rtcp_receiver_loss,
    rtcp_sender_report,
    rtp_header,
)


def test_avcc_configuration_and_access_unit() -> None:
    """Extract parameter sets and reject truncated length-prefixed samples."""
    extra = b"\x01\x64\x00\x32\xff\xe1\x00\x02\x67\x01\x01\x00\x02\x68\x02"
    assert avcc_configuration(extra) == (4, (b"\x67\x01", b"\x68\x02"))
    assert avcc_nalus(b"\x00\x00\x00\x02\x65\xaa", 4) == (b"\x65\xaa",)
    with pytest.raises(ValueError, match="Truncated"):
        avcc_nalus(b"\x00\x00\x00\x03\x65\xaa", 4)


def test_parameter_sets_use_stap_a() -> None:
    """SPS and PPS precede the IDR in an aggregated packet."""
    payloads = tuple(h264_payloads((b"\x67abc", b"\x68de", b"\x65frame"), 1000))
    assert payloads == (b"\x78\x00\x04\x67abc\x00\x03\x68de", b"\x65frame")


def test_fu_a_reassembles_original_nalu() -> None:
    """FU-A preserves the NAL header and all bytes within the payload limit."""
    original = b"\x65" + bytes(range(256)) * 20
    payloads = tuple(h264_payloads((original,), 1000))
    assert all(len(item) <= 1000 for item in payloads)
    assert payloads[0][1] & 0x80
    assert payloads[-1][1] & 0x40
    assert (
        bytes(((payloads[0][0] & 0xE0) | (payloads[0][1] & 31),))
        + b"".join(p[2:] for p in payloads)
        == original
    )


def test_srtp_context_roundtrip() -> None:
    """Libsrtp can authenticate and decrypt one generated packet."""
    libsrtp = pytest.importorskip("pylibsrtp")
    key = bytes(range(30))
    sender = NativeVideoSender(
        base64.b64encode(key).decode(), 123, "127.0.0.1", 1234, 1200, 0
    )
    receiver = libsrtp.Session(
        libsrtp.Policy(key=key, ssrc_type=libsrtp.Policy.SSRC_ANY_INBOUND)
    )
    packet = struct.pack(">BBHII", 0x80, 99, 1, 200, 123) + b"\x65video"
    assert receiver.unprotect(sender._send_crypto.protect(packet)) == packet


def test_header_wrap_and_rtcp_loss() -> None:
    """Wrap RTP counters and read loss only for the matching SSRC."""
    assert struct.unpack(">BBHII", rtp_header(123, 65536, 2**32, True)) == (
        128,
        227,
        0,
        0,
        123,
    )
    report = (
        struct.pack(">BBHII", 0x81, 201, 7, 456, 123) + bytes((7, 0, 0, 3)) + bytes(16)
    )
    assert rtcp_receiver_loss(report, 123) == (7, 3)
    assert rtcp_receiver_loss(report, 124) is None
    with pytest.raises(ValueError):
        rtcp_receiver_loss(report[:-1], 123)


def test_rtcp_rejects_tampered_authentication() -> None:
    """Authenticated RTCP detects modifications before report parsing."""
    libsrtp = pytest.importorskip("pylibsrtp")
    key = bytes(range(30))
    outbound = libsrtp.Session(
        libsrtp.Policy(key=key, ssrc_type=libsrtp.Policy.SSRC_ANY_OUTBOUND)
    )
    inbound = libsrtp.Session(
        libsrtp.Policy(key=key, ssrc_type=libsrtp.Policy.SSRC_ANY_INBOUND)
    )
    report = (
        struct.pack(">BBHII", 0x81, 201, 7, 456, 123) + bytes((7, 0, 0, 3)) + bytes(16)
    )
    protected = outbound.protect_rtcp(report)
    assert rtcp_receiver_loss(inbound.unprotect_rtcp(protected), 123) == (7, 3)
    tampered = protected[:-1] + bytes((protected[-1] ^ 1,))
    with pytest.raises(libsrtp.Error):
        inbound.unprotect_rtcp(tampered)


async def test_sender_encrypts_and_wraps_sequence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every packet is protected, ordered and wraps without nonce reuse."""
    libsrtp = pytest.importorskip("pylibsrtp")
    key = bytes(range(30))
    sender = NativeVideoSender(
        base64.b64encode(key).decode(), 123, "127.0.0.1", 1234, 1200, 0
    )
    sender._sequence = 65535
    receiver = libsrtp.Session(
        libsrtp.Policy(key=key, ssrc_type=libsrtp.Policy.SSRC_ANY_INBOUND)
    )

    class FakeSocket:
        def setblocking(self, _value: bool) -> None:
            pass

        def bind(self, _address: object) -> None:
            pass

        def close(self) -> None:
            pass

    async def wait_forever() -> None:
        await asyncio.Event().wait()

    async def media():
        yield b"init"
        yield b"part"

    sent: list[bytes] = []

    async def send(_sock: object, data: bytes, _address: object) -> None:
        sent.append(receiver.unprotect(data))

    monkeypatch.setattr(hksv_rtp.socket, "socket", lambda *_: FakeSocket())
    monkeypatch.setattr(
        hksv_rtp,
        "inspect_part",
        lambda *_: (hksv_rtp.AccessUnit(0, 0, 0.1, (b"\x65" + bytes(2000),)),),
    )
    monkeypatch.setattr(sender, "_receive_reports", wait_forever)
    monkeypatch.setattr(sender, "_sender_reports", wait_forever)
    monkeypatch.setattr(
        asyncio.get_running_loop(), "sock_sendto", AsyncMock(side_effect=send)
    )
    await sender.run(media())
    assert [struct.unpack_from(">H", packet, 2)[0] for packet in sent] == [65535, 0]
    assert [bool(packet[1] & 0x80) for packet in sent] == [False, True]


def test_sender_report_pairs_source_rtp_and_wall_clock() -> None:
    """Report the RTP clock at the actual time the related packet was sent."""
    report = rtcp_sender_report(123, 90000, 1000.5, 22, 3000)
    assert struct.unpack(">BBHIIIIII", report) == (
        0x80,
        200,
        6,
        123,
        2_208_989_800,
        2**31,
        90000,
        22,
        3000,
    )
