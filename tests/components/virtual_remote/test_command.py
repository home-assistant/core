"""Tests for virtual remote command parsing."""

import pytest

from homeassistant.components.virtual_remote.command import (
    CommandParseError,
    RawTiming,
    parse_remote_command,
    validate_raw_command,
    validate_remote_command_payload,
)
from homeassistant.exceptions import HomeAssistantError


def _timings(command) -> list[tuple[int, int]]:
    """Return command timings as tuples."""
    return [(timing.high_us, timing.low_us) for timing in command.get_raw_timings()]


def test_raw_timing_dataclass() -> None:
    """Test RawTiming stores mark/space pairs."""
    timing = RawTiming(high_us=1, low_us=2)
    assert timing.high_us == 1
    assert timing.low_us == 2


@pytest.mark.parametrize(
    ("payload", "kwargs", "modulation", "timings"),
    [
        ("9000,4500,560,560", {}, 38000, [(9000, 4500), (560, 560)]),
        ("38000:9000,4500,560,560", {}, 38000, [(9000, 4500), (560, 560)]),
        (
            "9000 4500 560 560",
            {"carrier_frequency": 40000},
            40000,
            [(9000, 4500), (560, 560)],
        ),
        (
            "[9000, 4500, 560, 560]",
            {"modulation": 36000},
            36000,
            [(9000, 4500), (560, 560)],
        ),
        (
            '{"timings": [9000, 4500, 560, 560]}',
            {"modulation": 36000},
            36000,
            [(9000, 4500), (560, 560)],
        ),
        (
            '{"carrier_frequency": 56000, "timings": [9000, 4500, 560, 560]}',
            {},
            56000,
            [(9000, 4500), (560, 560)],
        ),
        (
            '{"modulation": 57000, "timings": [9000, 4500, 560, 560]}',
            {},
            57000,
            [(9000, 4500), (560, 560)],
        ),
    ],
)
def test_parse_valid_commands(
    payload: str, kwargs: dict, modulation: int, timings: list[tuple[int, int]]
) -> None:
    """Test valid command payloads."""
    command = parse_remote_command(payload, kwargs)
    assert command.modulation == modulation
    assert _timings(command) == timings


def test_parse_pronto_command() -> None:
    """Test learned Pronto hex parsing."""
    command = parse_remote_command("0000 006D 0002 0000 0156 00AC 0015 0015")
    assert command.modulation == 38029
    assert _timings(command) == [(8993, 4523), (552, 552)]


@pytest.mark.parametrize(
    "payload",
    [
        "",
        "{}",
        "[]",
        "[9000]",
        "[9000, 0]",
        "[9000, -1]",
        "[9000, 4500, 560]",
        '[9000, "bad"]',
        '{"timings": "bad"}',
        '{"timings": [9000, 4500], "modulation": "bad"}',
        "{bad",
        "bad",
        "bad:9000,4500",
        "0000 0000 0001 0000 0001 0001",
        "0000 006D 0000 0000",
        "0000 006D 0001 0000 0000 0001",
        "0000 006D 0001 0000 0001",
    ],
)
def test_parse_invalid_commands_raise_home_assistant_error(payload: str) -> None:
    """Test invalid command payloads through public parser."""
    with pytest.raises(HomeAssistantError):
        parse_remote_command(payload)


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ("", "Command cannot be empty"),
        ("[9000]", "timings must contain mark/space pairs"),
        ("[9000, 0]", "timings must be greater than zero"),
        ("{}", "timings must be a list"),
        ("123", "timings must contain mark/space pairs"),
        ("bad:9000,4500", "Command modulation must be an integer"),
    ],
)
def test_validate_remote_command_payload_raises_command_parse_error(
    payload: str, message: str
) -> None:
    """Test options-flow validator preserves parser errors."""
    with pytest.raises(CommandParseError, match=message):
        validate_remote_command_payload(payload)


@pytest.mark.parametrize(
    ("modulation", "timings", "message"),
    [
        (0, [1, 2], "modulation must be greater than zero"),
        (38000, [], "timings cannot be empty"),
        (38000, [1], "timings must contain mark/space pairs"),
        (38000, [1, 0], "timings must be greater than zero"),
    ],
)
def test_validate_raw_command(
    modulation: int, timings: list[int], message: str
) -> None:
    """Test raw command field validation."""
    with pytest.raises(CommandParseError, match=message):
        validate_raw_command(modulation, timings)


def test_parse_remote_command_uses_custom_translation_domain() -> None:
    """Test parser supports reuse by other integrations."""
    with pytest.raises(HomeAssistantError) as err:
        parse_remote_command("", translation_domain="itachip2ir")

    assert err.value.translation_domain == "itachip2ir"
    assert err.value.translation_key == "remote_invalid_command"
