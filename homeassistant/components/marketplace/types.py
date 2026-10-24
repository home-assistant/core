"""Types for the Marketplace."""

from typing import TypedDict


class DownloadableContent(TypedDict):
    """Downloadable content."""

    url: str
    name: str
