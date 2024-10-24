"""Support for media browsing."""

from aiostreammagic import StreamMagicClient
from aiostreammagic.models import Preset

from homeassistant.components.media_player import BrowseMedia, MediaClass
from homeassistant.core import HomeAssistant

from .const import CAMBRIDGE_TO_MEDIA_CLASSES, CAMBRIDGE_TYPES_MAPPING, LOGGER


async def async_browse_media(
    hass: HomeAssistant,
    client: StreamMagicClient,
    media_content_id: str | None,
    media_content_type: str | None,
) -> BrowseMedia:
    """Browse media."""

    if media_content_type == "presets":
        return await _presets_payload(client.preset_list.presets)

    if media_content_type == "presets_folder":
        assert media_content_id
        return await _presets_folder_payload(
            client.preset_list.presets, media_content_id
        )

    return await _root_payload(
        hass,
        client,
    )


async def _root_payload(
    hass: HomeAssistant,
    client: StreamMagicClient,
) -> BrowseMedia:
    """Return root payload for Cambridge Audio."""
    children: list[BrowseMedia] = []

    if client.preset_list.presets:
        children.append(
            BrowseMedia(
                title="Presets",
                media_class=MediaClass.DIRECTORY,
                media_content_id="",
                media_content_type="presets",
                thumbnail="https://brands.home-assistant.io/_/cambridge_audio/logo.png",
                can_play=False,
                can_expand=True,
            )
        )

    if len(children) == 1:
        return await async_browse_media(
            hass,
            client,
            children[0].media_content_id,
            children[0].media_content_type,
        )

    return BrowseMedia(
        title="Cambridge Audio",
        media_class=MediaClass.DIRECTORY,
        media_content_id="",
        media_content_type="root",
        can_play=False,
        can_expand=True,
        children=children,
    )


async def _presets_payload(presets: list[Preset]) -> BrowseMedia:
    """Create payload to list presets."""

    children: list[BrowseMedia] = []

    class_types: set[str] = {preset.preset_class for preset in presets}
    content_types: set[str] = set()
    for class_type in sorted(class_types):
        try:
            content_types.add(CAMBRIDGE_TYPES_MAPPING[class_type])
        except KeyError:
            LOGGER.debug("Unknown class type received %s", class_type)
            continue
    for media_content_type in sorted(content_types):
        media_class = CAMBRIDGE_TO_MEDIA_CLASSES[media_content_type]
        children.append(
            BrowseMedia(
                title=media_content_type.title(),
                media_class=media_class,
                media_content_id=media_content_type,
                media_content_type="presets_folder",
                can_play=False,
                can_expand=True,
            )
        )

    return BrowseMedia(
        title="Presets",
        media_class=MediaClass.DIRECTORY,
        media_content_id="",
        media_content_type="presets",
        can_play=False,
        can_expand=True,
        children=children,
    )


async def _presets_folder_payload(
    presets: list[Preset], media_content_id: str
) -> BrowseMedia:
    """Create payload to list all items of a type favorite."""
    children: list[BrowseMedia] = []
    for preset in presets:
        media_content_type = CAMBRIDGE_TYPES_MAPPING.get(preset.preset_class, None)
        if not media_content_type or media_content_type != media_content_id:
            continue
        children.append(
            BrowseMedia(
                title=preset.name,
                media_class=CAMBRIDGE_TO_MEDIA_CLASSES[media_content_id],
                media_content_id=str(preset.preset_id),
                media_content_type="preset",
                can_play=True,
                can_expand=False,
                thumbnail=preset.art_url,
            )
        )

    return BrowseMedia(
        title=media_content_id.title(),
        media_class=MediaClass.DIRECTORY,
        media_content_id="",
        media_content_type="favorites",
        can_play=False,
        can_expand=True,
        children=children,
    )
