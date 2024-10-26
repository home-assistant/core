"""Support for media browsing."""

from aiostreammagic import StreamMagicClient
from aiostreammagic.models import Preset

from homeassistant.components.media_player import BrowseMedia, MediaClass
from homeassistant.core import HomeAssistant


async def async_browse_media(
    hass: HomeAssistant,
    client: StreamMagicClient,
    media_content_id: str | None,
    media_content_type: str | None,
) -> BrowseMedia:
    """Browse media."""

    if media_content_type == "presets":
        return await _presets_payload(client.preset_list.presets)

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
    for preset in presets:
        if preset.state != "OK":
            continue
        children.append(
            BrowseMedia(
                title=preset.name,
                media_class=MediaClass.MUSIC,
                media_content_id=str(preset.preset_id),
                media_content_type="preset",
                can_play=True,
                can_expand=False,
                thumbnail=preset.art_url,
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
