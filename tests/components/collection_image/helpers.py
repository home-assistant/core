"""Helper utilities for collection image tests."""

from homeassistant.components.collection_image.const import DOMAIN
from homeassistant.components.media_player import BrowseMedia, MediaClass
from homeassistant.components.media_source import BrowseMediaSource

from tests.common import MockConfigEntry


def config_entry_from_uri(uri: str | list[str]) -> MockConfigEntry:
    """Construct a mock config entry from one URI or a list of URIs."""

    def media_item(content_id: str) -> dict[str, str]:
        return {
            "media_content_id": content_id,
            "media_content_type": "",
        }

    media: dict[str, str] | list[dict[str, str]]
    if isinstance(uri, str):
        media = media_item(uri)
    else:
        media = [media_item(item) for item in uri]

    return MockConfigEntry(
        data={"media": media},
        domain=DOMAIN,
        title="Random Image",
    )


def image(
    media_content_id: str,
    *,
    title: str = "a picture",
) -> BrowseMedia:
    """Create a playable image browse result."""
    return BrowseMedia(
        media_class=MediaClass.IMAGE,
        media_content_id=media_content_id,
        media_content_type="image/png",
        title=title,
        can_play=True,
        can_expand=False,
    )


def directory(
    title: str,
    *children: BrowseMedia,
) -> BrowseMediaSource:
    """Create an expandable browse result."""
    return BrowseMediaSource(
        domain=None,
        identifier=None,
        media_class="",
        media_content_type="",
        title=title,
        can_play=False,
        can_expand=True,
        children=list(children),
    )
