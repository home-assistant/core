"""Tests for the Flipper IR parser."""

from __future__ import annotations

import pytest

from homeassistant.components.flipper_ir.parser import (
    InvalidIRFileError,
    parse_ir_file,
)


def test_parse_valid_file() -> None:
    """Parsing a valid file returns all commands in order."""
    content = (
        "Filetype: IR signals file\n"
        "Version: 1\n"
        "#\n"
        "name: Power\n"
        "type: parsed\n"
        "protocol: NEC\n"
        "address: 00 00 00 00\n"
        "command: 45 00 00 00\n"
        "#\n"
        "name: Vol_up\n"
        "type: parsed\n"
        "protocol: NEC\n"
    )
    commands = parse_ir_file(content)
    assert [c["name"] for c in commands] == ["Power", "Vol_up"]
    assert commands[0]["protocol"] == "NEC"


def test_parse_deduplicates_names() -> None:
    """Duplicate command names are dropped."""
    content = (
        "Filetype: IR signals file\n"
        "Version: 1\n"
        "#\n"
        "name: Power\n"
        "type: parsed\n"
        "#\n"
        "name: Power\n"
        "type: parsed\n"
        "#\n"
        "name: Mute\n"
        "type: parsed\n"
    )
    commands = parse_ir_file(content)
    assert [c["name"] for c in commands] == ["Power", "Mute"]


def test_parse_rejects_wrong_filetype() -> None:
    """Files without the expected header are rejected."""
    content = "Filetype: Sub-Ghz settings\nVersion: 1\n#\nname: Foo\n"
    with pytest.raises(InvalidIRFileError):
        parse_ir_file(content)


def test_parse_rejects_empty_file() -> None:
    """Empty files are rejected."""
    with pytest.raises(InvalidIRFileError):
        parse_ir_file("")


def test_parse_rejects_missing_header() -> None:
    """Files without a Filetype header are rejected."""
    content = "Version: 1\n#\nname: Power\n"
    with pytest.raises(InvalidIRFileError):
        parse_ir_file(content)


def test_parse_rejects_file_without_commands() -> None:
    """Files with only a header and no commands are rejected."""
    content = "Filetype: IR signals file\nVersion: 1\n"
    with pytest.raises(InvalidIRFileError):
        parse_ir_file(content)
