"""PowerShades UDP packet building and parsing.

Pure functions only — no sockets, no Home Assistant imports.

Packet layout (little-endian):
    Length(2) + CRC16-XMODEM(2) + Op(1) + Sequence(1) + Channel(1) + Reserved(1) + Payload
The CRC covers Op + Sequence + Channel + Reserved + Payload.
"""

from dataclasses import dataclass
import struct
from typing import TypedDict

from .const import OP_GET_STATUS


class SerialReply(TypedDict):
    """Parsed Get Serial Number reply."""

    model: int
    direction: int
    serial: int
    dhcp_enabled: bool


HEADER_SIZE = 8

CrcTable = [
    0x0000,
    0x1021,
    0x2042,
    0x3063,
    0x4084,
    0x50A5,
    0x60C6,
    0x70E7,
    0x8108,
    0x9129,
    0xA14A,
    0xB16B,
    0xC18C,
    0xD1AD,
    0xE1CE,
    0xF1EF,
    0x1231,
    0x0210,
    0x3273,
    0x2252,
    0x52B5,
    0x4294,
    0x72F7,
    0x62D6,
    0x9339,
    0x8318,
    0xB37B,
    0xA35A,
    0xD3BD,
    0xC39C,
    0xF3FF,
    0xE3DE,
    0x2462,
    0x3443,
    0x0420,
    0x1401,
    0x64E6,
    0x74C7,
    0x44A4,
    0x5485,
    0xA56A,
    0xB54B,
    0x8528,
    0x9509,
    0xE5EE,
    0xF5CF,
    0xC5AC,
    0xD58D,
    0x3653,
    0x2672,
    0x1611,
    0x0630,
    0x76D7,
    0x66F6,
    0x5695,
    0x46B4,
    0xB75B,
    0xA77A,
    0x9719,
    0x8738,
    0xF7DF,
    0xE7FE,
    0xD79D,
    0xC7BC,
    0x48C4,
    0x58E5,
    0x6886,
    0x78A7,
    0x0840,
    0x1861,
    0x2802,
    0x3823,
    0xC9CC,
    0xD9ED,
    0xE98E,
    0xF9AF,
    0x8948,
    0x9969,
    0xA90A,
    0xB92B,
    0x5AF5,
    0x4AD4,
    0x7AB7,
    0x6A96,
    0x1A71,
    0x0A50,
    0x3A33,
    0x2A12,
    0xDBFD,
    0xCBDC,
    0xFBBF,
    0xEB9E,
    0x9B79,
    0x8B58,
    0xBB3B,
    0xAB1A,
    0x6CA6,
    0x7C87,
    0x4CE4,
    0x5CC5,
    0x2C22,
    0x3C03,
    0x0C60,
    0x1C41,
    0xEDAE,
    0xFD8F,
    0xCDEC,
    0xDDCD,
    0xAD2A,
    0xBD0B,
    0x8D68,
    0x9D49,
    0x7E97,
    0x6EB6,
    0x5ED5,
    0x4EF4,
    0x3E13,
    0x2E32,
    0x1E51,
    0x0E70,
    0xFF9F,
    0xEFBE,
    0xDFDD,
    0xCFFC,
    0xBF1B,
    0xAF3A,
    0x9F59,
    0x8F78,
    0x9188,
    0x81A9,
    0xB1CA,
    0xA1EB,
    0xD10C,
    0xC12D,
    0xF14E,
    0xE16F,
    0x1080,
    0x00A1,
    0x30C2,
    0x20E3,
    0x5004,
    0x4025,
    0x7046,
    0x6067,
    0x83B9,
    0x9398,
    0xA3FB,
    0xB3DA,
    0xC33D,
    0xD31C,
    0xE37F,
    0xF35E,
    0x02B1,
    0x1290,
    0x22F3,
    0x32D2,
    0x4235,
    0x5214,
    0x6277,
    0x7256,
    0xB5EA,
    0xA5CB,
    0x95A8,
    0x8589,
    0xF56E,
    0xE54F,
    0xD52C,
    0xC50D,
    0x34E2,
    0x24C3,
    0x14A0,
    0x0481,
    0x7466,
    0x6447,
    0x5424,
    0x4405,
    0xA7DB,
    0xB7FA,
    0x8799,
    0x97B8,
    0xE75F,
    0xF77E,
    0xC71D,
    0xD73C,
    0x26D3,
    0x36F2,
    0x0691,
    0x16B0,
    0x6657,
    0x7676,
    0x4615,
    0x5634,
    0xD94C,
    0xC96D,
    0xF90E,
    0xE92F,
    0x99C8,
    0x89E9,
    0xB98A,
    0xA9AB,
    0x5844,
    0x4865,
    0x7806,
    0x6827,
    0x18C0,
    0x08E1,
    0x3882,
    0x28A3,
    0xCB7D,
    0xDB5C,
    0xEB3F,
    0xFB1E,
    0x8BF9,
    0x9BD8,
    0xABBB,
    0xBB9A,
    0x4A75,
    0x5A54,
    0x6A37,
    0x7A16,
    0x0AF1,
    0x1AD0,
    0x2AB3,
    0x3A92,
    0xFD2E,
    0xED0F,
    0xDD6C,
    0xCD4D,
    0xBDAA,
    0xAD8B,
    0x9DE8,
    0x8DC9,
    0x7C26,
    0x6C07,
    0x5C64,
    0x4C45,
    0x3CA2,
    0x2C83,
    0x1CE0,
    0x0CC1,
    0xEF1F,
    0xFF3E,
    0xCF5D,
    0xDF7C,
    0xAF9B,
    0xBFBA,
    0x8FD9,
    0x9FF8,
    0x6E17,
    0x7E36,
    0x4E55,
    0x5E74,
    0x2E93,
    0x3EB2,
    0x0ED1,
    0x1EF0,
]

# Get/Set flag payload for the Get PoE Shade Name command (0 = Get)
GET_SHADE_NAME_PAYLOAD = b"\x00"


def crc16_xmodem(data: bytes) -> int:
    """Calculate CRC16-XMODEM checksum."""
    crc = 0
    for b in data:
        crc = ((crc << 8) & 0xFFFF) ^ CrcTable[((crc >> 8) ^ b) & 0xFF]
    return crc


def build_packet(
    op: int, sequence: int = 0, channel: int = 0, payload: bytes = b""
) -> bytes:
    """Build a PowerShades UDP packet."""
    reserved = 0
    crc_data = struct.pack("<BBBB", op, sequence, channel, reserved) + payload
    crc = crc16_xmodem(crc_data)
    return (
        struct.pack("<HHBBBB", len(payload), crc, op, sequence, channel, reserved)
        + payload
    )


def build_set_position_payload(percent: int) -> bytes:
    """Build the payload for a Set Position packet."""
    mask = 0x0001  # MASK_PERCENT
    tilt = 0
    channel_mask = 0
    return struct.pack("<HhhI", mask, percent, tilt, channel_mask)


def build_set_limit_payload(limit_type: int) -> bytes:
    """Build the payload for a Set Limit packet."""
    return struct.pack("<H", limit_type)


def build_set_name_payload(name: str) -> bytes:
    """Build the payload for a Set PoE Shade Name packet."""
    return b"\x01" + name.encode("ascii")[:50].ljust(50, b"\x00")


@dataclass(frozen=True)
class PacketHeader:
    """Parsed packet header."""

    length: int
    crc: int
    op: int
    sequence: int
    channel: int


def parse_header(data: bytes) -> PacketHeader | None:
    """Parse a packet header, or return None if too short."""
    if len(data) < HEADER_SIZE:
        return None
    length, crc, op, sequence, channel, _reserved = struct.unpack(
        "<HHBBBB", data[:HEADER_SIZE]
    )
    return PacketHeader(length, crc, op, sequence, channel)


def verify_packet(data: bytes) -> bool:
    """Validate a packet's length field and CRC.

    The CRC covers Op + Sequence + Channel + Reserved + Payload for
    replies as well as commands (verified against real device replies).
    """
    header = parse_header(data)
    if header is None or len(data) < HEADER_SIZE + header.length:
        return False
    return crc16_xmodem(data[4 : HEADER_SIZE + header.length]) == header.crc


def parse_serial_reply(data: bytes) -> SerialReply | None:
    """Parse a Get Serial Number reply packet.

    Payload layout (after the 8-byte header): Model(1) Pad1(1) Pad2(1)
    Direction(1) SerialLow(4) SerialHigh(4) DhcpEnabled(1) IP(4)
    Subnet(4) Gateway(4) Internal(50).
    """
    if len(data) < 24:
        return None
    model = data[8]
    direction = data[11]
    serial_low = struct.unpack("<I", data[12:16])[0]
    serial_high = struct.unpack("<I", data[16:20])[0]
    dhcp_enabled = bool(data[20])
    return {
        "model": model,
        "direction": direction,
        "serial": (serial_high << 32) | serial_low,
        "dhcp_enabled": dhcp_enabled,
    }


def _decode_name(name_bytes: bytes) -> str | None:
    name = name_bytes.split(b"\x00")[0].decode("ascii", errors="ignore").strip()
    return name or None


def parse_device_name_reply(data: bytes) -> str | None:
    """Parse a Get Device Name (RF gateway) reply packet."""
    if len(data) < 58:  # 8-byte header + 50-byte name
        return None
    return _decode_name(data[8:58])


def parse_shade_name_reply(data: bytes) -> str | None:
    """Parse a Get PoE Shade Name reply packet."""
    if len(data) < 59:  # 8-byte header + 1-byte get/set flag + 50-byte name
        return None
    return _decode_name(data[9:59])


@dataclass(frozen=True)
class StatusReply:
    """Parsed status reply."""

    position: int | None
    battery_mv: int


def parse_status_reply(data: bytes) -> StatusReply | None:
    """Parse a Get Status reply packet."""
    header = parse_header(data)
    if header is None or header.op != OP_GET_STATUS:
        return None
    payload = data[HEADER_SIZE : HEADER_SIZE + header.length]
    if len(payload) < 30:
        return None
    (
        percent,
        _tilt,
        _memory,
        battery_mv,
        _time,
        _cycles,
        _stalls,
        _temperature,
        _raw_percent,
        _raw_tilt,
    ) = struct.unpack("<hhHHIIIhII", payload[:30])
    # The device reports percent as signed; treat out-of-range as unknown
    position = percent if 0 <= percent <= 100 else None
    return StatusReply(position=position, battery_mv=battery_mv)


def battery_percentage(battery_mv: int | None) -> int | None:
    """Convert battery voltage (mV) to a rough percentage (3.0V=0%, 4.2V=100%)."""
    if battery_mv is None:
        return None
    voltage = battery_mv / 1000.0
    if voltage <= 3.0:
        return 0
    if voltage >= 4.2:
        return 100
    return int((voltage - 3.0) / (4.2 - 3.0) * 100)
