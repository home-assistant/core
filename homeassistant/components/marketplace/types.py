"""Types for the Marketplace."""

from typing import TypedDict

from .utils.url import RemoteFile


class DownloadableContent(TypedDict):
    """Downloadable content."""

    url: RemoteFile
    name: str
