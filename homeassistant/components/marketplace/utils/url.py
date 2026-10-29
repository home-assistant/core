"""URL utilities for the Marketplace."""

import re
from typing import Any, Literal

GIT_SHA = re.compile(r"^[a-fA-F0-9]{40}$")

# How the Marketplace refers to a tag internally, GitHub URLs do not use it
TAG_REF_PREFIX = "tags/"


def ref_version(ref: str | None) -> str:
    """Return the tag or branch a ref points at, without the tag prefix."""
    return (ref or "").removeprefix(TAG_REF_PREFIX)


def github_release_asset(
    *,
    repository: str,
    version: str,
    filename: str,
    **_: Any,
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
    **_: Any,
) -> str:
    """Generate a download URL for a repository zip."""
    if GIT_SHA.match(version):
        return f"https://github.com/{repository}/archive/{version}.zip"
    return f"https://github.com/{repository}/archive/refs/{variant}/{version}.zip"


def github_commit_archive(*, repository: str, commit: str) -> str:
    """Generate a download URL for the zip of a repository at a commit.

    Unlike the refs of github_archive, an abbreviated commit SHA works here.
    """
    return f"https://github.com/{repository}/archive/{commit}.zip"
