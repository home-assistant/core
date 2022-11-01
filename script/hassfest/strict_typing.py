"""Ensure strict_typing file is valid and sorted."""
from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from .model import Config, Integration


def _sort_within_sections(line_iter: Iterable[str]) -> Iterable[str]:
    """
    Sort lines within sections (anything not delimited by a blank line
    or an octothorpe-prefixed comment line).
    """
    section: list[str] = []
    for line in line_iter:
        if line.startswith("#") or not line.strip():
            yield from sorted(section)
            section.clear()
            yield line
            continue
        section.append(line)
    yield from sorted(section)


def _get_strict_typing_path(config: Config) -> Path:
    return config.root / ".strict-typing"


def generate_and_validate(config: Config) -> str:
    """Validate and generate strict_typing."""
    lines = [
        line.strip()
        for line in _get_strict_typing_path(config).read_text().splitlines()
    ]
    return "\n".join(_sort_within_sections(lines)) + "\n"


def validate(integrations: dict[str, Integration], config: Config) -> None:
    """Validate strict_typing."""
    config.cache["strict_typing"] = content = generate_and_validate(config)

    config_path = _get_strict_typing_path(config)
    if config_path.read_text() != content:
        config.add_error(
            "strict_typing",
            "File .strict_typing is not up to date. Run python3 -m script.hassfest",
            fixable=True,
        )


def generate(integrations: dict[str, Integration], config: Config) -> None:
    """Generate strict_typing."""
    _get_strict_typing_path(config).write_text(config.cache["strict_typing"])
