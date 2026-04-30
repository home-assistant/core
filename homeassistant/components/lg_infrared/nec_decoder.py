"""NEC IR protocol decoding for the LG IR integration."""

from __future__ import annotations

from infrared_protocols import NECCommand

# NEC protocol timing constants (microseconds)
_LEADER_HIGH = 9000
_LEADER_LOW = 4500
_BIT_HIGH = 562
_ZERO_LOW = 562
_ONE_LOW = 1687
_REPEAT_LOW = 2250

# Tolerance for timing comparisons (±40%)
_TOLERANCE = 0.4


def _is_close(actual: int, expected: int) -> bool:
    """Check if an actual timing value is within tolerance of the expected value."""
    margin = expected * _TOLERANCE
    return expected - margin <= actual <= expected + margin


def _decode_bit(high_us: int, low_us: int) -> int | None:
    """Decode a single NEC data bit from high and low timings.

    Returns 0, 1, or None if the timings don't match a valid NEC bit.
    """
    if not _is_close(high_us, _BIT_HIGH):
        return None
    if _is_close(low_us, _ZERO_LOW):
        return 0
    if _is_close(low_us, _ONE_LOW):
        return 1
    return None


def _count_repeat_codes(timings: list[int], start_index: int) -> int:
    """Count NEC repeat codes starting from the given index.

    A repeat code consists of a leader burst (9000µs high, 2250µs low)
    followed by an end pulse (562µs high).
    """
    count = 0
    i = start_index
    while i + 2 < len(timings):
        if (
            _is_close(timings[i], _LEADER_HIGH)
            and _is_close(-timings[i + 1], _REPEAT_LOW)
            and _is_close(timings[i + 2], _BIT_HIGH)
        ):
            count += 1
            # Advance past the leader pair, the end pulse, and the trailing
            # gap (negative) that precedes the next repeat (if any).
            i += 4
        else:
            break
    return count


def from_raw_timings(timings: list[int]) -> NECCommand | None:
    """Decode raw IR timings into a NECCommand.

    Timings are an alternating list of positive (high pulse) and negative
    (low gap) durations in microseconds.

    Expects timings in the NEC protocol format:
    - Leader pulse: ~9000µs high, ~4500µs low
    - 32 data bits (LSB first): 562µs high + 562µs low (0) or 1687µs low (1)
    - End pulse: ~562µs high
    - Optional repeat codes: ~9000µs high, ~2250µs low + end pulse

    Returns a NECCommand if the timings match, or None otherwise.
    """
    # Minimum: 1 leader pair (2) + 32 bit pairs (64) + 1 end pulse high (1) = 67
    if len(timings) < 67:
        return None

    # Validate leader pulse
    if not _is_close(timings[0], _LEADER_HIGH) or not _is_close(
        -timings[1], _LEADER_LOW
    ):
        return None

    # Decode 32 data bits (LSB first)
    data = 0
    for i in range(32):
        bit = _decode_bit(timings[2 + 2 * i], -timings[3 + 2 * i])
        if bit is None:
            return None
        data |= bit << i

    # Validate end pulse
    if not _is_close(timings[66], _BIT_HIGH):
        return None

    # Extract bytes
    address_low = data & 0xFF
    address_high = (data >> 8) & 0xFF
    command_byte = (data >> 16) & 0xFF
    command_inverted = (data >> 24) & 0xFF

    # Validate command checksum
    if command_byte ^ command_inverted != 0xFF:
        return None

    # Reconstruct the full 16-bit address.
    # Standard NEC (8-bit address) and extended NEC (16-bit address) produce
    # identical timings when address_low ^ address_high == 0xFF, making them
    # indistinguishable from raw timings alone. We always return the 16-bit
    # representation; callers can check if the high byte is the complement
    # of the low byte to determine if it was originally a standard 8-bit address.
    address = address_low | (address_high << 8)

    # Count repeat codes after the end pulse, skipping the trailing gap
    # (negative) that follows it.
    repeat_count = _count_repeat_codes(timings, 68)

    return NECCommand(
        address=address,
        command=command_byte,
        modulation=0,
        repeat_count=repeat_count,
    )
