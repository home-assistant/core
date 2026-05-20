"""Tests for iTach IP2IR command parsing helpers."""

import pytest

from homeassistant.components.itachip2ir.command import (
    CommandParseError,
    RawInfraredCommand,
    _is_hex_word,
    _looks_like_pronto,
    _parse_json_command,
    _parse_pronto_command,
    parse_remote_command,
    validate_raw_command,
    validate_remote_command_payload,
)
from homeassistant.exceptions import HomeAssistantError


def _timings(command: RawInfraredCommand) -> list[tuple[int, int]]:
    """Return raw timings as tuples for assertions."""
    return [(timing.high_us, timing.low_us) for timing in command.get_raw_timings()]


def test_parse_json_list_uses_default_modulation() -> None:
    """Test a JSON timing list uses the default modulation."""
    command = parse_remote_command("[9000, 4500, 560, 560]")

    assert command.modulation == 38000
    assert _timings(command) == [(9000, 4500), (560, 560)]


def test_parse_json_object_uses_carrier_frequency_alias() -> None:
    """Test JSON command object accepts carrier_frequency."""
    command = parse_remote_command(
        '{"carrier_frequency": 40000, "timings": [100, 200]}'
    )

    assert command.modulation == 40000
    assert _timings(command) == [(100, 200)]


def test_parse_text_command_with_modulation_prefix() -> None:
    """Test text timing command with explicit modulation prefix."""
    command = parse_remote_command("56000:100 200 300 400")

    assert command.modulation == 56000
    assert _timings(command) == [(100, 200), (300, 400)]


def test_parse_pronto_command() -> None:
    """Test learned raw Pronto hex parsing."""
    command = parse_remote_command("0000 006D 0001 0000 0015 0016")

    assert command.modulation == 38029
    assert _timings(command) == [(552, 579)]


@pytest.mark.parametrize(
    ("raw_command", "error"),
    [
        ("", "Command cannot be empty"),
        ("{}", "timings must be a list"),
        ("123", "timings must contain mark/space pairs"),
        ("abc:def", "Command modulation must be an integer"),
        ("[100, 200, 300]", "timings must contain mark/space pairs"),
        ("[100, 0]", "timings must be greater than zero"),
        ("[100, -1]", "timings must be greater than zero"),
        (
            '{"modulation": "bad", "timings": [100, 200]}',
            "modulation must be an integer",
        ),
        ('{"timings": [""]}', "timings must not contain empty values"),
        ('{"timings": ["bad", 200]}', "timings must contain only integers"),
    ],
)
def test_parse_remote_command_wraps_parse_errors(
    raw_command: str,
    error: str,
) -> None:
    """Test public parser wraps parse failures in HomeAssistantError."""
    with pytest.raises(HomeAssistantError) as exc_info:
        parse_remote_command(raw_command)

    assert exc_info.value.translation_domain == "itachip2ir"
    assert exc_info.value.translation_key == "remote_invalid_command"
    assert exc_info.value.translation_placeholders == {"error": error}


@pytest.mark.parametrize(
    ("raw_command", "error"),
    [
        ("{}", "timings must be a list"),
        ("[100]", "timings must contain mark/space pairs"),
    ],
)
def test_validate_remote_command_payload_raises_raw_parser_error(
    raw_command: str,
    error: str,
) -> None:
    """Test payload validation exposes raw parser errors."""
    with pytest.raises(CommandParseError, match=error):
        validate_remote_command_payload(raw_command)


@pytest.mark.parametrize(
    "raw_command",
    [
        "[100, 200]",
        '{"timings": [100, 200]}',
        "100,200",
        "38000:100,200",
        "0000 006D 0001 0000 0015 0016",
    ],
)
def test_validate_remote_command_payload_accepts_supported_payloads(
    raw_command: str,
) -> None:
    """Test payload validation accepts all supported command forms."""
    validate_remote_command_payload(raw_command)


@pytest.mark.parametrize(
    ("modulation", "timings", "error"),
    [
        (0, [100, 200], "modulation must be greater than zero"),
        (-1, [100, 200], "modulation must be greater than zero"),
        (38000, [], "timings cannot be empty"),
        (38000, [100], "timings must contain mark/space pairs"),
        (38000, [100, 0], "timings must be greater than zero"),
    ],
)
def test_validate_raw_command_rejects_invalid_fields(
    modulation: int,
    timings: list[int],
    error: str,
) -> None:
    """Test raw command field validation."""
    with pytest.raises(CommandParseError, match=error):
        validate_raw_command(modulation, timings)


@pytest.mark.parametrize(
    ("word", "expected"),
    [
        ("0000", True),
        ("00ff", True),
        ("FFFF", True),
        ("FFF", False),
        ("FFFFF", False),
        ("zzzz", False),
    ],
)
def test_is_hex_word(word: str, expected: bool) -> None:
    """Test 16-bit hex word detection."""
    assert _is_hex_word(word) is expected


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("0000 006D 0001 0000", True),
        ("0001 006D 0001 0000", False),
        ("0000 006D 0001", False),
        ("0000 006D 0001 zzzz", False),
    ],
)
def test_looks_like_pronto(command: str, expected: bool) -> None:
    """Test raw Pronto command detection."""
    assert _looks_like_pronto(command) is expected


@pytest.mark.parametrize(
    ("raw_command", "error"),
    [
        ("0000 006D 0000 0000", "Pronto command is too short"),
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
            "0000 006D 0001 0000 0015 0000",
            "Pronto timing words must be greater than zero",
        ),
    ],
)
def test_pronto_validation_errors(raw_command: str, error: str) -> None:
    """Test Pronto parser validation errors."""
    with pytest.raises(HomeAssistantError) as exc_info:
        parse_remote_command(raw_command)

    assert exc_info.value.translation_placeholders == {"error": error}


def test_non_raw_pronto_falls_back_to_text_parser() -> None:
    """Test non-0000 Pronto-like payload is handled as text timings."""
    with pytest.raises(HomeAssistantError) as exc_info:
        parse_remote_command("0100 006D 0001 0000 0015 0016")

    assert exc_info.value.translation_placeholders == {
        "error": "timings must contain only integers"
    }


def test_parse_remote_command_accepts_kwargs_modulation() -> None:
    """Test modulation can be supplied through service kwargs."""
    command = parse_remote_command("100,200", {"modulation": "56000"})

    assert command.modulation == 56000
    assert _timings(command) == [(100, 200)]


def test_parse_remote_command_accepts_kwargs_carrier_frequency() -> None:
    """Test carrier_frequency can be supplied through service kwargs."""
    command = parse_remote_command("100,200", {"carrier_frequency": "40000"})

    assert command.modulation == 40000
    assert _timings(command) == [(100, 200)]


def test_parse_remote_command_rejects_invalid_kwargs_modulation() -> None:
    """Test invalid kwargs modulation raises translated error."""
    with pytest.raises(HomeAssistantError) as exc_info:
        parse_remote_command("100,200", {"modulation": "bad"})

    assert exc_info.value.translation_placeholders == {
        "error": "modulation must be an integer"
    }


def test_parse_json_command_rejects_primitive_json_payload() -> None:
    """Test JSON parser rejects primitive JSON payloads."""
    with pytest.raises(
        CommandParseError, match="Command JSON must be an object or timing array"
    ):
        _parse_json_command("123", 38_000)


def test_parse_pronto_command_rejects_unsupported_pronto_type() -> None:
    """Test raw Pronto parser rejects unsupported Pronto types."""
    with pytest.raises(
        CommandParseError,
        match="Only learned raw Pronto commands beginning with 0000 are supported",
    ):
        _parse_pronto_command("0100 006D 0001 0000 0015 0016")
