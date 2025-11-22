"""Support for Russound media browsing."""

from aiorussound import RussoundClient, Zone
from aiorussound.const import FeatureFlag
from aiorussound.util import is_feature_supported

from homeassistant.components.media_player import BrowseMedia, MediaClass
from homeassistant.core import HomeAssistant


async def async_browse_media(
    hass: HomeAssistant,
    client: RussoundClient,
    media_content_id: str | None,
    media_content_type: str | None,
    zone: Zone,
) -> BrowseMedia:
    """Browse media."""
    if media_content_type == "presets":
        return await _presets_payload(_find_presets_by_zone(client, zone))

    return await _root_payload(hass, _find_presets_by_zone(client, zone))


async def _root_payload(
    hass: HomeAssistant, presets_by_zone: dict[int, dict[int, str]]
) -> BrowseMedia:
    """Return root payload for Russound RIO."""
    children: list[BrowseMedia] = []

    if presets_by_zone:
        children.append(
            BrowseMedia(
                title="Presets",
                media_class=MediaClass.DIRECTORY,
                media_content_id="",
                media_content_type="presets",
                thumbnail="https://brands.home-assistant.io/_/russound_rio/logo.png",
                can_play=False,
                can_expand=True,
            )
        )

    return BrowseMedia(
        title="Russound",
        media_class=MediaClass.DIRECTORY,
        media_content_id="",
        media_content_type="root",
        can_play=False,
        can_expand=True,
        children=children,
    )


async def _presets_payload(presets_by_zone: dict[int, dict[int, str]]) -> BrowseMedia:
    """Create payload to list presets."""
    children: list[BrowseMedia] = []
    for source_id, presets in presets_by_zone.items():
        for preset_id, preset_name in presets.items():
            children.append(
                BrowseMedia(
                    title=preset_name,
                    media_class=MediaClass.CHANNEL,
                    media_content_id=f"{source_id},{preset_id}",
                    media_content_type="preset",
                    can_play=True,
                    can_expand=False,
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


def _find_presets_by_zone(
    client: RussoundClient, zone: Zone
) -> dict[int, dict[int, str]]:
    """Returns a dict by {source_id: {preset_id: preset_name}}."""
    assert client.rio_version
    return {
        source_id: source.presets
        for source_id, source in client.sources.items()
        if source.presets
        and (
            not is_feature_supported(
                client.rio_version, FeatureFlag.SUPPORT_ZONE_SOURCE_EXCLUSION
            )
            or source_id in zone.enabled_sources
        )
    }
