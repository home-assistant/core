"""URL utilities for the Community store."""

import re
from typing import Literal

GIT_SHA = re.compile(r"^[a-fA-F0-9]{40}$")


def github_release_asset(
    *,
    repository: str,
    version: str,
    filename: str,
    **_,
) -> str:
    """Generate a download URL for a release asset."""
    return f"https://github.com/{repository}/releases/download/{version}/{filename}"


def github_raw_file(*, repository: str, ref: str | None, path: str) -> str:
    """Generate a download URL for a file in a repository."""
    return f"https://raw.githubusercontent.com/{repository}/{ref}/{path}"


def github_archive(
    *,
    repository: str,
    version: str,
    variant: Literal["heads", "tags"] = "heads",
    **_,
) -> str:
    """Generate a download URL for a repository zip."""
    if GIT_SHA.match(version):
        return f"https://github.com/{repository}/archive/{version}.zip"
    return f"https://github.com/{repository}/archive/refs/{variant}/{version}.zip"
