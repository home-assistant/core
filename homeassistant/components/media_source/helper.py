"""Helpers for media source."""

from collections.abc import Callable

from homeassistant.components.media_player import (
    BrowseError,
    BrowseMedia,
    SearchMedia,
    SearchMediaQuery,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.frame import report_usage
from homeassistant.helpers.typing import UNDEFINED, UndefinedType

from .const import DOMAIN
from .error import UnknownMediaSource, Unresolvable
from .models import (
    BrowseMediaSource,
    MediaSourceItem,
    PlayMedia,
    RootBrowseMediaSource,
    _async_get_media_source,
    _async_get_media_sources,
)


async def _get_media_item(
    hass: HomeAssistant, media_content_id: str | None, target_media_player: str | None
) -> MediaSourceItem:
    """Return media item."""
    if media_content_id:
        item = MediaSourceItem.from_uri(hass, media_content_id, target_media_player)
    else:
        # We default to our own domain if its only one registered
        sources = await _async_get_media_sources(hass)
        domain = None if len(sources) > 1 else DOMAIN
        return MediaSourceItem(hass, domain, "", target_media_player)

    if (
        item.domain is not None
        and await _async_get_media_source(hass, item.domain) is None
    ):
        raise UnknownMediaSource(
            translation_domain=DOMAIN,
            translation_key="unknown_media_source",
            translation_placeholders={"domain": item.domain},
        )

    return item


async def async_browse_media(
    hass: HomeAssistant,
    media_content_id: str | None,
    *,
    content_filter: Callable[[BrowseMedia], bool] | None = None,
) -> BrowseMediaSource | RootBrowseMediaSource:
    """Return media player browse media results."""
    if DOMAIN not in hass.config.top_level_components:
        raise BrowseError("Media Source not loaded")

    try:
        media_item = await _get_media_item(hass, media_content_id, None)
        item = await media_item.async_browse()
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


async def async_search_media(
    hass: HomeAssistant,
    media_content_id: str | None,
    query: SearchMediaQuery,
) -> SearchMedia:
    """Return media searched in the media source."""
    if DOMAIN not in hass.config.top_level_components:
        raise BrowseError("Media Source not loaded")

    try:
        media_item = await _get_media_item(hass, media_content_id, None)
        return await media_item.async_search(query)
    except NotImplementedError as err:
        raise BrowseError(
            translation_domain=DOMAIN,
            translation_key="search_not_supported",
            translation_placeholders={"media_content_id": str(media_content_id)},
        ) from err
    except ValueError as err:
        raise BrowseError(
            translation_domain=DOMAIN,
            translation_key="search_media_failed",
            translation_placeholders={
                "media_content_id": str(media_content_id),
                "error": str(err),
            },
        ) from err


async def async_resolve_media(
    hass: HomeAssistant,
    media_content_id: str,
    target_media_player: str | None | UndefinedType = UNDEFINED,
) -> PlayMedia:
    """Get info to play media."""
    if DOMAIN not in hass.config.top_level_components:
        raise Unresolvable("Media Source not loaded")

    if target_media_player is UNDEFINED:
        report_usage(
            "calls media_source.async_resolve_media without passing an entity_id",
            exclude_integrations={DOMAIN},
        )
        target_media_player = None

    try:
        item = await _get_media_item(hass, media_content_id, target_media_player)
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
