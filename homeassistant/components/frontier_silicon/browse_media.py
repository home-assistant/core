"""Support for media browsing."""
import logging

from afsapi import AFSAPI, FSApiException, OutOfRangeException, Preset

from homeassistant.components.media_player import BrowseError, BrowseMedia
from homeassistant.components.media_player.const import (
    MEDIA_CLASS_CHANNEL,
    MEDIA_CLASS_DIRECTORY,
    MEDIA_TYPE_CHANNEL,
)

from .const import MEDIA_TYPE_PRESET

MEDIA_TYPE_TITLES = {
    MEDIA_TYPE_CHANNEL: "Channels",
    MEDIA_TYPE_PRESET: "Presets",
}

FSAPI_ITEM_TYPE_TO_MEDIA_CLASS = {
    0: MEDIA_CLASS_DIRECTORY,
    1: MEDIA_CLASS_CHANNEL,
    2: MEDIA_CLASS_CHANNEL,
}

_LOGGER = logging.getLogger(__name__)


def _item_preset_payload(preset: Preset, parent_key=None) -> BrowseMedia:
    """
    Create response payload for a single media item.

    Used by async_browse_media.
    """
    return BrowseMedia(
        title=preset.name,
        media_class=MEDIA_CLASS_CHANNEL,
        media_content_type=MEDIA_TYPE_PRESET,
        # We add 1 to the preset key to keep it in sync with the numbering shown
        # on the interface of the device
        media_content_id=f"{parent_key}/{int(preset.key)+1}",
        can_play=True,
        can_expand=False,
    )


def _item_payload(key, item: dict[str, str], parent_key=None) -> BrowseMedia:
    """
    Create response payload for a single media item.

    Used by async_browse_media.
    """
    assert "label" in item or "name" in item
    assert "type" in item

    title = item.get("label") or item.get("name") or "Unknown"
    title = title.strip()

    media_content_id = f"{parent_key}/{key}" if parent_key else key
    media_class = (
        FSAPI_ITEM_TYPE_TO_MEDIA_CLASS.get(int(item["type"])) or MEDIA_CLASS_CHANNEL
    )

    return BrowseMedia(
        title=title,
        media_class=media_class,
        media_content_type=MEDIA_TYPE_CHANNEL,
        media_content_id=media_content_id,
        can_play=(media_class != MEDIA_CLASS_DIRECTORY),
        can_expand=(media_class == MEDIA_CLASS_DIRECTORY),
    )


async def browse_top_level(current_mode, afsapi: AFSAPI):
    """
    Create response payload to describe contents of a specific library.

    Used by async_browse_media.
    """

    children = [
        BrowseMedia(
            title=name,
            media_class=MEDIA_CLASS_DIRECTORY,
            media_content_type=type_,
            # latter can happen if initialisation has not been fully done yet.
            media_content_id=current_mode or "unknown",
            can_play=False,
            can_expand=True,
        )
        for type_, name in MEDIA_TYPE_TITLES.items()
    ]

    library_info = BrowseMedia(
        media_class=MEDIA_CLASS_DIRECTORY,
        media_content_id="library",
        media_content_type="library",
        title="Media Library",
        can_play=False,
        can_expand=True,
        children=children,
        children_media_class=MEDIA_CLASS_DIRECTORY,
    )

    return library_info


async def browse_node(
    afsapi: AFSAPI,
    media_content_type,
    media_content_id,
):
    """List the contents of a navigation directory (or preset list) on a Frontier Silicon device."""

    title = MEDIA_TYPE_TITLES.get(media_content_type, "Unknown")
    parent_key = media_content_id

    children = []
    try:
        if media_content_type == MEDIA_TYPE_PRESET:
            # Return the presets

            children = [
                _item_preset_payload(preset, parent_key=parent_key)
                for preset in await afsapi.get_presets()
            ]

        else:
            # Browse to correct folder
            keys = media_content_id.split("/")
            await afsapi.nav_select_folder_via_path(keys[1:])

            # Return items in this folder
            children = [
                _item_payload(key, item, parent_key=parent_key)
                async for key, item in await afsapi.nav_list()
            ]
    except OutOfRangeException as err:
        _LOGGER.exception(err)
        raise BrowseError("The requested item is out of range") from err
    except FSApiException as err:
        _LOGGER.exception(err)
        raise BrowseError(str(err)) from err

    return BrowseMedia(
        title=title,
        media_content_id=media_content_id,
        media_content_type=MEDIA_TYPE_CHANNEL,
        media_class=MEDIA_CLASS_DIRECTORY,
        can_play=False,
        can_expand=True,
        children=children,
        children_media_class=MEDIA_CLASS_CHANNEL,
    )
