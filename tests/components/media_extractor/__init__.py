"""The tests for Media Extractor integration."""
from typing import Any

from tests.common import load_json_object_fixture
from tests.components.media_extractor.const import AUDIO_QUERY


def _get_base_fixture(url: str) -> str:
    return {"https://www.youtube.com/watch?v=dQw4w9WgXcQ": "youtube_1"}[url]


def _get_query_fixture(query: str | None) -> str:
    return {AUDIO_QUERY: "_bestaudio", "best": ""}.get(query, "")


class MockYoutubeDL:
    """Mock object for YoutubeDL."""

    _fixture = None

    def __init__(self, params: dict[str, Any]) -> None:
        """Initialize mock object for YoutubeDL."""
        self.params = params

    def extract_info(self, url: str, *, process: bool = False) -> dict[str, Any]:
        """Return info."""
        self._fixture = _get_base_fixture(url)
        return load_json_object_fixture(f"media_extractor/{self._fixture}_info.json")

    def process_ie_result(
        self, selected_media: dict[str, Any], *, download: bool = False
    ) -> dict[str, Any]:
        """Return result."""
        query_fixture = _get_query_fixture(self.params["format"])
        return load_json_object_fixture(
            f"media_extractor/{self._fixture}_result{query_fixture}.json"
        )
