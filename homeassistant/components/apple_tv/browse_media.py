"""Support for media browsing."""
from typing import Any

from homeassistant.components.media_player import BrowseMedia, MediaClass, MediaType


def build_app_list(app_list: dict[str, str]) -> BrowseMedia:
    """Create response payload for app list."""
    media_list = [
        {"app_id": app_id, "title": app_name, "type": MediaType.APP}
        for app_name, app_id in app_list.items()
    ]

    return BrowseMedia(
        media_class=MediaClass.DIRECTORY,
        media_content_id="apps",
        media_content_type=MediaType.APPS,
        title="Apps",
        can_play=False,
        can_expand=True,
        children=[item_payload(item) for item in media_list],
        children_media_class=MediaClass.APP,
    )


def item_payload(item: dict[str, Any]) -> BrowseMedia:
    """Create response payload for a single media item.

    Used by async_browse_media.
    """
    return BrowseMedia(
        title=item["title"],
        media_class=MediaClass.APP,
        media_content_type=MediaType.APP,
        media_content_id=item["app_id"],
        can_play=False,
        can_expand=False,
    )
