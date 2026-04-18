"""Parser for Flipper Zero IR signal files."""

from __future__ import annotations


class InvalidIRFileError(Exception):
    """Raised when the uploaded file is not a valid Flipper IR file."""


def parse_ir_file(content: str) -> list[dict[str, str]]:
    """Parse a Flipper Zero IR file and return a list of command dicts.

    The file format uses ``#`` as a separator between signal entries and
    ``key: value`` lines within each entry. The header must declare
    ``Filetype: IR signals file``. Each entry must contain a ``name`` field.
    """
    lines = content.splitlines()
    if not lines:
        raise InvalidIRFileError("File is empty")

    header_seen = False
    commands: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    seen_names: set[str] = set()

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#"):
            if current is not None:
                _finalize(current, commands, seen_names)
                current = None
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if key == "Filetype":
            if value != "IR signals file":
                raise InvalidIRFileError(f"Unsupported filetype: {value}")
            header_seen = True
            continue
        if key == "Version":
            continue
        if current is None:
            current = {}
        current[key] = value

    if current is not None:
        _finalize(current, commands, seen_names)

    if not header_seen:
        raise InvalidIRFileError("Missing 'Filetype: IR signals file' header")
    if not commands:
        raise InvalidIRFileError("No commands found in file")
    return commands


def _finalize(
    entry: dict[str, str], commands: list[dict[str, str]], seen_names: set[str]
) -> None:
    """Validate and append an entry to the commands list."""
    name = entry.get("name")
    if not name:
        return
    if name in seen_names:
        return
    seen_names.add(name)
    commands.append(entry)
