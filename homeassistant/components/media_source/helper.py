"""Helpers for media source."""

from __future__ import annotations

from collections.abc import Callable

from homeassistant.components.media_player import BrowseError, BrowseMedia
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.frame import report_usage
from homeassistant.helpers.typing import UNDEFINED, UndefinedType
from homeassistant.loader import bind_hass

from .const import DOMAIN, MEDIA_SOURCE_DATA
from .error import UnknownMediaSource, Unresolvable
from .models import BrowseMediaSource, MediaSourceItem, PlayMedia


@callback
def _get_media_item(
    hass: HomeAssistant, media_content_id: str | None, target_media_player: str | None
) -> MediaSourceItem:
    """Return media item."""
    if media_content_id:
        item = MediaSourceItem.from_uri(hass, media_content_id, target_media_player)
    else:
        # We default to our own domain if its only one registered
        domain = None if len(hass.data[MEDIA_SOURCE_DATA]) > 1 else DOMAIN
        return MediaSourceItem(hass, domain, "", target_media_player)

    if item.domain is not None and item.domain not in hass.data[MEDIA_SOURCE_DATA]:
        raise UnknownMediaSource(
            translation_domain=DOMAIN,
            translation_key="unknown_media_source",
            translation_placeholders={"domain": item.domain},
        )

    return item


@bind_hass
async def async_browse_media(
    hass: HomeAssistant,
    media_content_id: str | None,
    *,
    content_filter: Callable[[BrowseMedia], bool] | None = None,
) -> BrowseMediaSource:
    """Return media player browse media results."""
    if DOMAIN not in hass.data:
        raise BrowseError("Media Source not loaded")

    try:
        item = await _get_media_item(hass, media_content_id, None).async_browse()
    except ValueError as err:
        raise BrowseError(
            translation_domain=DOMAIN,
            translation_key="browse_media_failed",
            translation_placeholders={
                "media_content_id": str(media_content_id),
                "error": str(err),
            },
        ) from err

    if content_filter is None or item.children is None:
        return item

    old_count = len(item.children)
    item.children = [
        child for child in item.children if child.can_expand or content_filter(child)
    ]
    item.not_shown += old_count - len(item.children)
    return item


@bind_hass
async def async_resolve_media(
    hass: HomeAssistant,
    media_content_id: str,
    target_media_player: str | None | UndefinedType = UNDEFINED,
) -> PlayMedia:
    """Get info to play media."""
    if DOMAIN not in hass.data:
        raise Unresolvable("Media Source not loaded")

    if target_media_player is UNDEFINED:
        report_usage(
            "calls media_source.async_resolve_media without passing an entity_id",
            exclude_integrations={DOMAIN},
        )
        target_media_player = None

    try:
        item = _get_media_item(hass, media_content_id, target_media_player)
    except ValueError as err:
        raise Unresolvable(
            translation_domain=DOMAIN,
            translation_key="resolve_media_failed",
            translation_placeholders={
                "media_content_id": str(media_content_id),
                "error": str(err),
            },
        ) from err

    return await item.async_resolve()
