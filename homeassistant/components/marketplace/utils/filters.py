"""Filter functions."""

from typing import Any

from aiogithubapi.models.git_tree import GitHubGitTreeEntryModel

from .tree import tree_entry_filename, tree_entry_is_directory


def filter_content_return_one_of_type(
    content: list[Any],
    namestartswith: str,
    filterfiltype: str,
    attr: str = "name",
) -> list[Any]:
    """Only match 1 of the filter."""
    contents: list[Any] = []
    filetypefound = False
    for filename in content:
        if isinstance(filename, str):
            if filename.startswith(namestartswith):
                if filename.endswith(f".{filterfiltype}"):
                    if not filetypefound:
                        contents.append(filename)
                        filetypefound = True
                    continue
                contents.append(filename)
        elif getattr(filename, attr).startswith(namestartswith):
            if getattr(filename, attr).endswith(f".{filterfiltype}"):
                if not filetypefound:
                    contents.append(filename)
                    filetypefound = True
                continue
            contents.append(filename)
    return contents


def get_first_directory_in_directory(
    content: list[GitHubGitTreeEntryModel], dirname: str
) -> str | None:
    """Return the first directory in dirname or None."""
    directory: str | None = None
    for entry in content:
        if entry.path.startswith(dirname) and entry.path != dirname:
            if tree_entry_is_directory(entry):
                directory = tree_entry_filename(entry)
                break
    return directory
