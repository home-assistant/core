"""Helpers for the entries of a repository tree."""

import posixpath

from aiogithubapi.models.git_tree import GitHubGitTreeEntryModel


def tree_entry_filename(entry: GitHubGitTreeEntryModel) -> str:
    """Return the file name of a tree entry, without its directories."""
    path: str = entry.path
    return posixpath.basename(path)


def tree_entry_directory(entry: GitHubGitTreeEntryModel) -> str:
    """Return the directory of a tree entry, empty in the repository root."""
    path: str = entry.path
    return posixpath.dirname(path)


def tree_entry_is_directory(entry: GitHubGitTreeEntryModel) -> bool:
    """Return if a tree entry is a directory."""
    entry_type: str = entry.type
    return entry_type == "tree"
