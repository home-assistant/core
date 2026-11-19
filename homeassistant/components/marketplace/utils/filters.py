"""Filter functions."""

from aiogithubapi.models.git_tree import GitHubGitTreeEntryModel

from .tree import tree_entry_filename, tree_entry_is_directory


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
