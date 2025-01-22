"""Support for media browsing."""

import logging

from afsapi import AFSAPI, FSApiException, OutOfRangeException, Preset

from homeassistant.components.media_player import (
    BrowseError,
    BrowseMedia,
    MediaClass,
    MediaType,
)

from .const import MEDIA_CONTENT_ID_CHANNELS, MEDIA_CONTENT_ID_PRESET

TOP_LEVEL_DIRECTORIES = {
    MEDIA_CONTENT_ID_CHANNELS: "Channels",
    MEDIA_CONTENT_ID_PRESET: "Presets",
}

FSAPI_ITEM_TYPE_TO_MEDIA_CLASS = {
    0: MediaClass.DIRECTORY,
    1: MediaClass.CHANNEL,
    2: MediaClass.CHANNEL,
}

_LOGGER = logging.getLogger(__name__)


def _item_preset_payload(preset: Preset, player_mode: str) -> BrowseMedia:
    """Create response payload for a single media item.

    Used by async_browse_media.
    """
    return BrowseMedia(
        title=preset.name,
        media_class=MediaClass.CHANNEL,
        media_content_type=MediaType.CHANNEL,
        # We add 1 to the preset key to keep it in sync with the numbering shown
        # on the interface of the device
        media_content_id=(
            f"{player_mode}/{MEDIA_CONTENT_ID_PRESET}/{int(preset.key) + 1}"
        ),
        can_play=True,
        can_expand=False,
    )


def _item_payload(
    key, item: dict[str, str], player_mode: str, parent_keys: list[str]
) -> BrowseMedia:
    """Create response payload for a single media item.

    Used by async_browse_media.
    """
    assert "label" in item or "name" in item
    assert "type" in item

    title = item.get("label") or item.get("name") or "Unknown"
    title = title.strip()

    media_content_id = "/".join(
        [player_mode, MEDIA_CONTENT_ID_CHANNELS, *parent_keys, key]
    )
    media_class = (
        FSAPI_ITEM_TYPE_TO_MEDIA_CLASS.get(int(item["type"])) or MediaClass.CHANNEL
    )

    return BrowseMedia(
        title=title,
        media_class=media_class,
        media_content_type=MediaClass.CHANNEL,
        media_content_id=media_content_id,
        can_play=(media_class != MediaClass.DIRECTORY),
        can_expand=(media_class == MediaClass.DIRECTORY),
    )


async def browse_top_level(current_mode, afsapi: AFSAPI):
    """Create response payload to describe contents of a specific library.

    Used by async_browse_media.
    """

    children = [
        BrowseMedia(
            title=name,
            media_class=MediaClass.DIRECTORY,
            media_content_type=MediaType.CHANNELS,
            media_content_id=(
                f"{current_mode or 'unknown'}/{top_level_media_content_id}"
            ),
            can_play=False,
            can_expand=True,
        )
        for top_level_media_content_id, name in TOP_LEVEL_DIRECTORIES.items()
    ]

    return BrowseMedia(
        media_class=MediaClass.DIRECTORY,
        media_content_id="library",
        media_content_type=MediaType.CHANNELS,
        title="Media Library",
        can_play=False,
        can_expand=True,
        children=children,
        children_media_class=MediaClass.DIRECTORY,
    )


async def browse_node(
    afsapi: AFSAPI,
    media_content_type,
    media_content_id,
):
    """List the contents of a navigation directory (or preset list)."""

    player_mode, browse_type, *parent_keys = media_content_id.split("/")

    title = TOP_LEVEL_DIRECTORIES.get(browse_type, "Unknown")

    children = []
    try:
        if browse_type == MEDIA_CONTENT_ID_PRESET:
            # Return the presets

            children = [
                _item_preset_payload(preset, player_mode=player_mode)
                for preset in await afsapi.get_presets()
            ]

        else:
            # Browse to correct folder
            await afsapi.nav_select_folder_via_path(parent_keys)

            # Return items in this folder
            children = [
                _item_payload(key, item, player_mode, parent_keys=parent_keys)
                async for key, item in await afsapi.nav_list()
            ]
    except OutOfRangeException as err:
        raise BrowseError("The requested item is out of range") from err
    except FSApiException as err:
        raise BrowseError(str(err)) from err

    return BrowseMedia(
        title=title,
        media_content_id=media_content_id,
        media_content_type=MediaType.CHANNELS,
        media_class=MediaClass.DIRECTORY,
        can_play=False,
        can_expand=True,
        children=children,
        children_media_class=MediaType.CHANNEL,
    )
