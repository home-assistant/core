"""Tests for legacy iTach command parsing."""

from __future__ import annotations

import pytest

from homeassistant.components.itach import command as command_module
from homeassistant.components.itach.command import (
    PRONTO_FREQUENCY_REFERENCE_US,
    CommandParseError,
    RawTiming,
    _is_hex_word,
    _looks_like_pronto,
    _parse_pronto_command,
    _validate_raw_command,
    parse_pronto_command,
)

VALID_PRONTO = "0000 006D 0002 0001 0156 00AB 0015 0041 0015 0016"


def _expected_modulation(frequency_word: int) -> int:
    """Return expected Pronto carrier frequency."""
    return round(1_000_000 / (frequency_word * PRONTO_FREQUENCY_REFERENCE_US))


def _expected_timing(word: int, frequency_word: int) -> int:
    """Return expected Pronto timing in microseconds."""
    return round(word * frequency_word * PRONTO_FREQUENCY_REFERENCE_US)


def test_parse_pronto_command_returns_modulation_and_raw_timing_pairs() -> None:
    """Test parsing learned raw Pronto hex into raw timing pairs."""
    parsed = parse_pronto_command(VALID_PRONTO)

    assert parsed.modulation == _expected_modulation(0x006D)
    assert parsed.get_raw_timings() == [
        RawTiming(
            high_us=_expected_timing(0x0156, 0x006D),
            low_us=_expected_timing(0x00AB, 0x006D),
        ),
        RawTiming(
            high_us=_expected_timing(0x0015, 0x006D),
            low_us=_expected_timing(0x0041, 0x006D),
        ),
        RawTiming(
            high_us=_expected_timing(0x0015, 0x006D),
            low_us=_expected_timing(0x0016, 0x006D),
        ),
    ]


def test_parse_pronto_command_strips_input_and_accepts_lowercase_hex() -> None:
    """Test parsing ignores surrounding whitespace and accepts lowercase hex."""
    parsed = parse_pronto_command("  0000 006d 0001 0000 0015 0016  ")

    assert parsed.modulation == _expected_modulation(0x006D)
    assert parsed.get_raw_timings() == [
        RawTiming(
            high_us=_expected_timing(0x0015, 0x006D),
            low_us=_expected_timing(0x0016, 0x006D),
        )
    ]


@pytest.mark.parametrize(
    ("pronto", "match"),
    [
        ("", "Command cannot be empty"),
        (
            "sendir-on",
            "Only learned raw Pronto commands beginning with 0000 are supported",
        ),
        (
            "0000 006D 0000 0001",
            "Pronto command is too short",
        ),
        (
            "0000 0000 0001 0000 0015 0016",
            "Pronto frequency word must be greater than zero",
        ),
        (
            "0000 006D 0000 0000 0015 0016",
            "Pronto command must declare at least one timing pair",
        ),
        (
            "0000 006D 0002 0000 0015 0016",
            "Pronto command timing word count does not match the declared lengths",
        ),
        (
            "0000 006D 0001 0000 0000 0016",
            "Pronto timing words must be greater than zero",
        ),
    ],
)
def test_parse_pronto_command_rejects_invalid_commands(pronto: str, match: str) -> None:
    """Test invalid Pronto command data raises parser errors."""
    with pytest.raises(CommandParseError, match=match):
        parse_pronto_command(pronto)


def test_parse_pronto_command_rejects_unsupported_pronto_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test unsupported Pronto command types are rejected defensively."""
    monkeypatch.setattr(command_module, "_looks_like_pronto", lambda words: True)

    with pytest.raises(
        CommandParseError,
        match="Only learned raw Pronto commands beginning with 0000 are supported",
    ):
        _parse_pronto_command("0100 006D 0001 0000 0015 0016")


@pytest.mark.parametrize(
    ("modulation", "timings", "match"),
    [
        (0, [1, 2], "modulation must be greater than zero"),
        (38_000, [], "timings cannot be empty"),
        (38_000, [1], "timings must contain mark/space pairs"),
        (38_000, [1, 0], "timings must be greater than zero"),
    ],
)
def test_validate_raw_command_rejects_invalid_fields(
    modulation: int, timings: list[int], match: str
) -> None:
    """Test raw command validation errors."""
    with pytest.raises(CommandParseError, match=match):
        _validate_raw_command(modulation, timings)


def test_validate_raw_command_accepts_valid_fields() -> None:
    """Test raw command validation accepts valid fields."""
    _validate_raw_command(38_000, [1, 2])


@pytest.mark.parametrize(
    ("word", "expected"),
    [
        ("0000", True),
        ("abcd", True),
        ("000", False),
        ("zzzz", False),
    ],
)
def test_is_hex_word(word: str, expected: bool) -> None:
    """Test Pronto hex-word detection."""
    assert _is_hex_word(word) is expected


@pytest.mark.parametrize(
    ("words", "expected"),
    [
        (["0000", "006D", "0001"], False),
        (["0100", "006D", "0001", "0000"], False),
        (["0000", "zzzz", "0001", "0000"], False),
        (["0000", "006D", "0001", "0000"], True),
    ],
)
def test_looks_like_pronto(words: list[str], expected: bool) -> None:
    """Test raw learned Pronto command detection."""
    assert _looks_like_pronto(words) is expected
