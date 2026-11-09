"""URL utilities for the Marketplace."""

from dataclasses import dataclass
import re
from typing import Any, Literal, override

from yarl import URL

from ..profiles import Endpoint

GIT_SHA = re.compile(r"^[a-fA-F0-9]{40}$")

# How the Marketplace refers to a tag internally, GitHub URLs do not use it
TAG_REF_PREFIX = "tags/"


@dataclass(frozen=True, slots=True)
class RemoteFile:
    """A file to download, by its path on an endpoint of the download profile.

    The host is not part of it, the download picks it from the profile.
    """

    endpoint: Endpoint
    path: str

    @override
    def __str__(self) -> str:
        """Return the path, how the file is named in logs and errors."""
        return self.path


def ref_version(ref: str | None) -> str:
    """Return the tag or branch a ref points at, without the tag prefix."""
    return (ref or "").removeprefix(TAG_REF_PREFIX)


def github_release_asset(
    *,
    repository: str,
    version: str,
    filename: str,
    **_: Any,
) -> RemoteFile:
    """Return a release asset to download."""
    return RemoteFile(
        Endpoint.GITHUB, f"{repository}/releases/download/{version}/{filename}"
    )


def github_listed_release_asset(
    *, repository: str, version: str, filename: str, url: str | None
) -> RemoteFile:
    """Return a release asset the API listed, by the path GitHub encoded for it.

    Only the path, the host comes from the profile like for any download.
    """
    path = URL(url).raw_path if url else ""
    if path.startswith(f"/{repository}/releases/download/"):
        return RemoteFile(Endpoint.GITHUB, path.removeprefix("/"))
    return github_release_asset(
        repository=repository, version=version, filename=filename
    )


def github_raw_file(*, repository: str, ref: str | None, path: str) -> RemoteFile:
    """Return a file in a repository to download."""
    return RemoteFile(Endpoint.RAW, f"{repository}/{ref}/{path}")


def github_archive(
    *,
    repository: str,
    version: str,
    variant: Literal["heads", "tags"] = "heads",
    **_: Any,
) -> RemoteFile:
    """Return the zip of a repository to download."""
    if GIT_SHA.match(version):
        return RemoteFile(Endpoint.GITHUB, f"{repository}/archive/{version}.zip")
    return RemoteFile(
        Endpoint.GITHUB, f"{repository}/archive/refs/{variant}/{version}.zip"
    )


def github_commit_archive(*, repository: str, commit: str) -> RemoteFile:
    """Return the zip of a repository at a commit to download.

    Unlike the refs of github_archive, an abbreviated commit SHA works here.
    """
    return RemoteFile(Endpoint.GITHUB, f"{repository}/archive/{commit}.zip")
