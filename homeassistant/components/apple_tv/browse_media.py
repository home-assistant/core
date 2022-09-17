"""Support for media browsing."""

from homeassistant.components.media_player import BrowseMedia
from homeassistant.components.media_player.const import (
    MEDIA_CLASS_APP,
    MEDIA_CLASS_DIRECTORY,
    MEDIA_TYPE_APP,
    MEDIA_TYPE_APPS,
)


def build_app_list(app_list):
    """Create response payload for app list."""
    app_list = [
        {"app_id": app_id, "title": app_name, "type": MEDIA_TYPE_APP}
        for app_name, app_id in app_list.items()
    ]

    return BrowseMedia(
        media_class=MEDIA_CLASS_DIRECTORY,
        media_content_id="apps",
        media_content_type=MEDIA_TYPE_APPS,
        title="Apps",
        can_play=False,
        can_expand=True,
        children=[item_payload(item) for item in app_list],
        children_media_class=MEDIA_CLASS_APP,
    )


def item_payload(item):
    """
    Create response payload for a single media item.

    Used by async_browse_media.
    """
    return BrowseMedia(
        title=item["title"],
        media_class=MEDIA_CLASS_APP,
        media_content_type=MEDIA_TYPE_APP,
        media_content_id=item["app_id"],
        can_play=False,
        can_expand=False,
    )
