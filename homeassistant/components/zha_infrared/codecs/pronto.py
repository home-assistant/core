"""Pronto Hex codec helpers."""

from typing import Any


def encode_raw_to_pronto_hex(timings: list[int], modulation: int | None = None) -> str:
    """Encode raw timings to Pronto Hex format."""
    if len(timings) < 2:
        raise ValueError("Pronto codec requires at least one pulse/space pair")

    carrier_hz = modulation or 38000
    if carrier_hz <= 0:
        raise ValueError("Carrier frequency must be positive")

    freq_word = round(1_000_000 / (carrier_hz * 0.241246))
    if freq_word <= 0:
        raise ValueError("Computed invalid Pronto frequency word")

    pulses = [abs(value) for value in timings]
    if len(pulses) % 2 == 1:
        pulses = pulses[:-1]

    burst_units: list[int] = []
    for duration_us in pulses:
        units = max(1, round((duration_us * carrier_hz) / 1_000_000))
        burst_units.append(min(units, 0xFFFF))

    intro_pairs = len(burst_units) // 2
    words = [0x0000, freq_word, intro_pairs, 0x0000, *burst_units]
    return " ".join(f"{word:04X}" for word in words)


def decode_pronto_hex_to_raw_timings(payload: Any) -> list[int] | None:
    """Decode Pronto Hex payload into alternating signed timings."""
    if not isinstance(payload, str):
        return None

    parts = payload.strip().split()
    if len(parts) < 4:
        return None
    try:
        words = [int(part, 16) for part in parts]
    except ValueError:
        return None

    if words[0] != 0x0000:
        return None
    freq_word = words[1]
    if freq_word <= 0:
        return None

    burst_words = words[4:]
    if not burst_words:
        return None

    carrier_hz = 1_000_000 / (freq_word * 0.241246)
    timings: list[int] = []
    for index, units in enumerate(burst_words):
        duration_us = round((units * 1_000_000) / carrier_hz)
        timings.append(duration_us if index % 2 == 0 else -duration_us)
    return timings
