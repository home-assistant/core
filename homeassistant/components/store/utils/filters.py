"""Filter functions."""

from __future__ import annotations

from typing import Any


def filter_content_return_one_of_type(
    content: list[str | Any],
    namestartswith: str,
    filterfiltype: str,
    attr: str = "name",
) -> list[str]:
    """Only match 1 of the filter."""
    contents = []
    filetypefound = False
    for filename in content:
        if isinstance(filename, str):
            if filename.startswith(namestartswith):
                if filename.endswith(f".{filterfiltype}"):
                    if not filetypefound:
                        contents.append(filename)
                        filetypefound = True
                    continue
                else:
                    contents.append(filename)
        else:
            if getattr(filename, attr).startswith(namestartswith):
                if getattr(filename, attr).endswith(f".{filterfiltype}"):
                    if not filetypefound:
                        contents.append(filename)
                        filetypefound = True
                    continue
                else:
                    contents.append(filename)
    return contents


def get_first_directory_in_directory(content: list[str | Any], dirname: str) -> str | None:
    """Return the first directory in dirname or None."""
    directory = None
    for path in content:
        if path.full_path.startswith(dirname) and path.full_path != dirname:
            if path.is_directory:
                directory = path.filename
                break
    return directory
