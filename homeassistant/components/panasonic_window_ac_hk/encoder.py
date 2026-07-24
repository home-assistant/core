"""Panasonic window A/C infrared encoder (Hong Kong / Macau CW-HU/HZ/SU/SUL).

Pure-Python, no Home Assistant dependencies, so it can be unit-tested in
isolation and (eventually) contributed to the infrared-protocols library.

Implements the reverse-engineered Panasonic CW-series protocol (see the
integration documentation on home-assistant.io). The 27-byte full state frame
and the 16-byte Quiet/Powerful short frames are both produced here as
protocol-agnostic microsecond timings: a flat ``list[int]`` where a positive
value is a pulse (carrier on) and a negative value is a space (carrier off),
matching the Home Assistant ``infrared`` platform convention.
"""

# --- Physical-layer timings, in microseconds (canonical Panasonic values) ----
HEADER_MARK = 3456
HEADER_SPACE = 1728
BIT_MARK = 432
ZERO_SPACE = 432
ONE_SPACE = 1296
SECTION_GAP = 10000  # between Frame 1 and Frame 2 (~10 ms)
MESSAGE_GAP = 100000  # trailing, after Frame 2 (~100 ms)

CARRIER_HZ = 38000

# --- Semantic field maps (from the spec) ------------------------------------
MODE_NIBBLE = {"auto": 0x0, "dry": 0x2, "cool": 0x3, "heat": 0x4}
FAN_NIBBLE = {
    "auto": 0xA,
    "low": 0x3,
    "mediumLow": 0x4,
    "medium": 0x5,
    "mediumHigh": 0x6,
    "high": 0x7,
}
SWING_NIBBLE = {"auto": 0xF, "fixed": 0x5}

MIN_TEMP = 16
MAX_TEMP = 30

NANOEX_BYTE = 25
NANOEX_MASK = 0x04

# Short-frame command payloads (bytes 12..14), keyed by toggle kind.
_SHORT_PAYLOAD = {
    "quiet": [0x80, 0x81, 0x33],
    "powerful": [0x80, 0x86, 0x35],
}


def checksum(state: list[int], start: int, end: int) -> int:
    """Sum bytes ``state[start..end]`` (inclusive) modulo 256."""
    total = 0
    for i in range(start, end + 1):
        total = (total + state[i]) & 0xFF
    return total


def build_full_frame(
    *,
    off: bool = False,
    mode: str,
    temp: float,
    fan: str,
    swing: str,
    nanoex: bool,
) -> list[int]:
    """Build the 27-byte full state frame from semantic parameters.

    ``temp`` is in degrees Celsius; byte 14 stores ``round(temp * 2)`` so the
    protocol's 0.5 C step is preserved.
    """
    state = [0] * 27
    # Frame 1 (constant preamble).
    for i, value in enumerate([0x02, 0x20, 0xE0, 0x04, 0x00, 0x00, 0x00, 0x06]):
        state[i] = value
    # Frame 2.
    state[8] = 0x02
    state[9] = 0x20
    state[10] = 0xE0
    state[11] = 0x04
    state[12] = 0x00
    state[13] = (MODE_NIBBLE[mode] << 4) | (0 if off else 1)
    state[14] = round(temp * 2)
    state[15] = 0x80
    state[16] = (FAN_NIBBLE[fan] << 4) | SWING_NIBBLE[swing]
    state[17] = 0x0D
    state[18] = 0x00
    state[19] = 0x0E
    state[20] = 0xE0
    state[21] = 0x00
    state[22] = 0x00
    state[23] = 0x81
    state[24] = 0x00
    state[25] = 0x02 | (NANOEX_MASK if nanoex else 0x00)
    state[26] = checksum(state, 8, 25)
    return state


def build_short_frame(kind: str) -> list[int]:
    """Build the 16-byte Quiet/Powerful toggle frame (no mode/temp/fan/swing)."""
    try:
        payload = _SHORT_PAYLOAD[kind]
    except KeyError:
        raise ValueError(f"unknown short-frame kind: {kind!r}") from None
    state = [
        0x02,
        0x20,
        0xE0,
        0x04,
        0x00,
        0x00,
        0x00,
        0x06,  # Frame 1
        0x02,
        0x20,
        0xE0,
        0x04,  # Frame 2 magic
        *payload,
    ]
    state.append(checksum(state, 8, 14))
    return state


def _bits_lsb(byte: int) -> list[int]:
    """Return the 8 bits of ``byte``, least-significant first."""
    return [(byte >> j) & 1 for j in range(8)]


def _frame_timings(frame: list[int], trailing_gap: int) -> list[int]:
    """Encode one frame (header + LSB-first bits + trailing mark/gap)."""
    timings = [HEADER_MARK, -HEADER_SPACE]
    for byte in frame:
        for bit in _bits_lsb(byte):
            timings.append(BIT_MARK)
            timings.append(-(ONE_SPACE if bit else ZERO_SPACE))
    timings.append(BIT_MARK)
    timings.append(-trailing_gap)
    return timings


def frame_to_timings(state: list[int]) -> list[int]:
    """Convert a state byte list into signed microsecond timings.

    Frame 1 is the first 8 bytes; Frame 2 is the remainder. A 27-byte full
    frame and a 16-byte short frame both work (the split is always at byte 8).
    """
    frame1 = state[:8]
    frame2 = state[8:]
    return [
        *_frame_timings(frame1, SECTION_GAP),
        *_frame_timings(frame2, MESSAGE_GAP),
    ]
