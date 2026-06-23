"""LG AC IR encoder and decoder — LG 28-bit protocol.

Frame layout (28 bits, MSB first):
  bits 27-20: 0x88 signature
  bits 19-16: command upper nibble
  bits 15-12: command lower nibble
  bits 11-8:  temperature field (temp_c - 15, valid 0-15)
  bits 7-4:   fan speed nibble
  bits 3-0:   checksum (sum of nibbles 1-6, low 4 bits)

Power-on/mode-change commands use LG 28-bit standard header (8500/4250 µs).
Power-off uses LG2 short header (3200/9900 µs) as transmitted by the physical remote.
"""

from typing import TypedDict

from homeassistant.components.climate import HVACMode


class AcState(TypedDict):
    """Decoded AC state from IR signal."""

    mode: HVACMode
    fan: str
    temp_c: int | None


# LG 28-bit standard timing (µs) — used for all on/mode commands
_HDR_MARK = 8500
_HDR_SPACE = 4250
# LG2 short header — used for power-off only (matches physical remote capture)
_OFF_HDR_MARK = 3200
_OFF_HDR_SPACE = 9900
# Shared bit timings (µs)
_BIT_MARK = 550
_BIT_ONE_SPACE = 1600
_BIT_ZERO_SPACE = 550

_BASE = 0x8800000
_BITS = 28

_CMD_ON_COOL = 0x00000
_CMD_ON_DRY = 0x01000
_CMD_ON_FAN = 0x02000
_CMD_ON_HEAT = 0x04000
_CMD_COOL = 0x08000
_CMD_DRY = 0x09000
_CMD_FAN = 0x0A000
_CMD_HEAT = 0x0C000
_CMD_OFF = 0xC0000

_FAN_TO_BITS: dict[str, int] = {
    "auto": 0x50,
    "quiet": 0x10,
    "low": 0x00,
    "medium": 0x20,
    "high": 0x40,
}
_FAN_BITS_TO_STR: dict[int, str] = {v: k for k, v in _FAN_TO_BITS.items()}

# Dry mode always encodes fixed 24 °C regardless of setpoint — verified from captures
_DRY_TEMP_FIELD = 0x900

# Decode: (nibble4, nibble3) → HVACMode
_CMD_NIBS_TO_MODE: dict[tuple[int, int], HVACMode] = {
    (0, 0x0): HVACMode.COOL,
    (0, 0x8): HVACMode.COOL,
    (0, 0x1): HVACMode.DRY,
    (0, 0x9): HVACMode.DRY,
    (0, 0x2): HVACMode.FAN_ONLY,
    (0, 0xA): HVACMode.FAN_ONLY,
    (0, 0x4): HVACMode.HEAT,
    (0, 0xC): HVACMode.HEAT,
    (0xC, 0x0): HVACMode.OFF,
}

# Header tolerance for decoding (µs)
_HDR_TOLERANCE = 2000


def _checksum(value: int) -> int:
    total = sum((value >> (i * 4)) & 0xF for i in range(1, 7))
    return value | (total & 0xF)


def _encode_frame(frame: int, hdr_mark: int, hdr_space: int) -> list[int]:
    timings: list[int] = [hdr_mark, -hdr_space]
    for i in range(_BITS - 1, -1, -1):
        bit = (frame >> i) & 1
        timings.append(_BIT_MARK)
        timings.append(-(_BIT_ONE_SPACE if bit else _BIT_ZERO_SPACE))
    timings.append(_BIT_MARK)
    return timings


def _encode_mode(cmd: int, fan: str, temp_field: int = 0) -> list[int]:
    frame = _checksum(_BASE | cmd | _FAN_TO_BITS.get(fan, 0x50) | temp_field)
    return _encode_frame(frame, _HDR_MARK, _HDR_SPACE)


def encode_off() -> list[int]:
    """Encode power-off command."""
    frame = _checksum(_BASE | _CMD_OFF | 0x50)
    return _encode_frame(frame, _OFF_HDR_MARK, _OFF_HDR_SPACE)


def encode_cool(temp_c: int, fan: str) -> list[int]:
    """Encode cool mode."""
    return _encode_mode(_CMD_ON_COOL, fan, max(0, min(15, temp_c - 15)) << 8)


def encode_heat(temp_c: int, fan: str) -> list[int]:
    """Encode heat mode."""
    return _encode_mode(_CMD_ON_HEAT, fan, max(0, min(15, temp_c - 15)) << 8)


def encode_dry(fan: str) -> list[int]:
    """Encode dry mode (temperature is fixed at 24 °C by protocol)."""
    return _encode_mode(_CMD_ON_DRY, fan, _DRY_TEMP_FIELD)


def encode_fan_only(fan: str) -> list[int]:
    """Encode fan-only mode."""
    return _encode_mode(_CMD_ON_FAN, fan)


def decode_timings(
    timings: list[int],
) -> AcState | None:
    """Decode raw LG AC IR timings to state dict.

    Returns {"mode": HVACMode, "fan": str, "temp_c": int | None} or None
    if the frame is not a recognised LG AC command.
    """
    if len(timings) < 58:  # header(2) + 28 bit pairs(56)
        return None

    hdr_mark = timings[0]
    hdr_space = abs(timings[1])

    # Accept LG-standard (~8500/4250) or LG2-short (~3200/9900)
    is_standard = (
        _HDR_MARK - _HDR_TOLERANCE <= hdr_mark <= _HDR_MARK + _HDR_TOLERANCE
        and _HDR_SPACE - _HDR_TOLERANCE <= hdr_space <= _HDR_SPACE + _HDR_TOLERANCE
    )
    is_lg2 = (
        _OFF_HDR_MARK - _HDR_TOLERANCE <= hdr_mark <= _OFF_HDR_MARK + _HDR_TOLERANCE
        and _OFF_HDR_SPACE - _HDR_TOLERANCE
        <= hdr_space
        <= _OFF_HDR_SPACE + _HDR_TOLERANCE
    )
    if not is_standard and not is_lg2:
        return None

    frame = 0
    i = 2
    bits_read = 0
    while i + 1 < len(timings) and bits_read < _BITS:
        frame = (frame << 1) | (1 if abs(timings[i + 1]) > 1000 else 0)
        i += 2
        bits_read += 1

    # Validate LG AC signature: top 8 bits must be 0x88
    if frame >> 20 != 0x88:
        return None

    nibs = [(frame >> (j * 4)) & 0xF for j in range(7)]

    # Validate checksum
    if sum(nibs[1:7]) & 0xF != nibs[0]:
        return None

    mode = _CMD_NIBS_TO_MODE.get((nibs[4], nibs[3]))
    if mode is None:
        return None

    fan = _FAN_BITS_TO_STR.get(nibs[1] << 4, "auto")
    temp_c: int | None = None
    if mode not in (HVACMode.OFF, HVACMode.DRY, HVACMode.FAN_ONLY) and nibs[2] > 0:
        temp_c = nibs[2] + 15

    return AcState(mode=mode, fan=fan, temp_c=temp_c)
