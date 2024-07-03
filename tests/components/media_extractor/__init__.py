"""The tests for Media Extractor integration."""

from typing import Any

from .const import (
    AUDIO_QUERY,
    NO_FORMATS_RESPONSE,
    SOUNDCLOUD_TRACK,
    YOUTUBE_EMPTY_PLAYLIST,
    YOUTUBE_PLAYLIST,
    YOUTUBE_VIDEO,
)

from tests.common import load_json_object_fixture


def _get_base_fixture(url: str) -> str:
    return {
        YOUTUBE_VIDEO: "youtube_1",
        YOUTUBE_PLAYLIST: "youtube_playlist",
        YOUTUBE_EMPTY_PLAYLIST: "youtube_empty_playlist",
        SOUNDCLOUD_TRACK: "soundcloud",
        NO_FORMATS_RESPONSE: "no_formats",
    }[url]


def _get_query_fixture(query: str | None) -> str:
    return {AUDIO_QUERY: "_bestaudio", "best": ""}.get(query, "")


class MockYoutubeDL:
    """Mock object for YoutubeDL."""

    _fixture = None

    def __init__(self, params: dict[str, Any]) -> None:
        """Initialize mock object for YoutubeDL."""
        self.params = params

    def extract_info(
        self, url: str, *, download: bool = True, process: bool = False
    ) -> dict[str, Any]:
        """Return info."""
        self._fixture = _get_base_fixture(url)
        if not download:
            return load_json_object_fixture(f"media_extractor/{self._fixture}.json")
        return load_json_object_fixture(f"media_extractor/{self._fixture}_info.json")

    def process_ie_result(
        self, selected_media: dict[str, Any], *, download: bool = False
    ) -> dict[str, Any]:
        """Return result."""
        query_fixture = _get_query_fixture(self.params["format"])
        return load_json_object_fixture(
            f"media_extractor/{self._fixture}_result{query_fixture}.json"
        )
