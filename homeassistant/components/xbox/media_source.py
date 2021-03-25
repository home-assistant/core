"""Xbox Media Source Implementation."""
from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass

from pydantic.error_wrappers import ValidationError  # pylint: disable=no-name-in-module
from xbox.webapi.api.client import XboxLiveClient
from xbox.webapi.api.provider.catalog.models import FieldsTemplate, Image
from xbox.webapi.api.provider.gameclips.models import GameclipsResponse
from xbox.webapi.api.provider.screenshots.models import ScreenshotResponse
from xbox.webapi.api.provider.smartglass.models import InstalledPackage

from homeassistant.components.media_player.const import (
    MEDIA_CLASS_DIRECTORY,
    MEDIA_CLASS_GAME,
    MEDIA_CLASS_IMAGE,
    MEDIA_CLASS_VIDEO,
)
from homeassistant.components.media_source.const import MEDIA_MIME_TYPES
from homeassistant.components.media_source.models import (
    BrowseMediaSource,
    MediaSource,
    MediaSourceItem,
    PlayMedia,
)
from homeassistant.core import callback
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.util import dt as dt_util

from .browse_media import _find_media_image
from .const import DOMAIN

MIME_TYPE_MAP = {
    "gameclips": "video/mp4",
    "screenshots": "image/png",
}

MEDIA_CLASS_MAP = {
    "gameclips": MEDIA_CLASS_VIDEO,
    "screenshots": MEDIA_CLASS_IMAGE,
}


async def async_get_media_source(hass: HomeAssistantType):
    """Set up Xbox media source."""
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    client = hass.data[DOMAIN][entry.entry_id]["client"]
    return XboxSource(hass, client)


@callback
def async_parse_identifier(
    item: MediaSourceItem,
) -> tuple[str, str, str]:
    """Parse identifier."""
    identifier = item.identifier or ""
    start = ["", "", ""]
    items = identifier.lstrip("/").split("~~", 2)
    return tuple(items + start[len(items) :])


@dataclass
class XboxMediaItem:
    """Represents gameclip/screenshot media."""

    caption: str
    thumbnail: str
    uri: str
    media_class: str


class XboxSource(MediaSource):
    """Provide Xbox screenshots and gameclips as media sources."""

    name: str = "Xbox Game Media"

    def __init__(self, hass: HomeAssistantType, client: XboxLiveClient):
        """Initialize Xbox source."""
        super().__init__(DOMAIN)

        self.hass: HomeAssistantType = hass
        self.client: XboxLiveClient = client

    async def async_resolve_media(self, item: MediaSourceItem) -> PlayMedia:
        """Resolve media to a url."""
        _, category, url = async_parse_identifier(item)
        kind = category.split("#", 1)[1]
        return PlayMedia(url, MIME_TYPE_MAP[kind])

    async def async_browse_media(
        self, item: MediaSourceItem, media_types: tuple[str] = MEDIA_MIME_TYPES
    ) -> BrowseMediaSource:
        """Return media."""
        title, category, _ = async_parse_identifier(item)

        if not title:
            return await self._build_game_library()

        if not category:
            return _build_categories(title)

        return await self._build_media_items(title, category)

    async def _build_game_library(self):
        """Display installed games across all consoles."""
        apps = await self.client.smartglass.get_installed_apps()
        games = {
            game.one_store_product_id: game
            for game in apps.result
            if game.is_game and game.title_id
        }

        app_details = await self.client.catalog.get_products(
            games.keys(),
            FieldsTemplate.BROWSE,
        )

        images = {
            prod.product_id: prod.localized_properties[0].images
            for prod in app_details.products
        }

        return BrowseMediaSource(
            domain=DOMAIN,
            identifier="",
            media_class=MEDIA_CLASS_DIRECTORY,
            media_content_type="",
            title="Xbox Game Media",
            can_play=False,
            can_expand=True,
            children=[_build_game_item(game, images) for game in games.values()],
            children_media_class=MEDIA_CLASS_GAME,
        )

    async def _build_media_items(self, title, category):
        """Fetch requested gameclip/screenshot media."""
        title_id, _, thumbnail = title.split("#", 2)
        owner, kind = category.split("#", 1)

        items: list[XboxMediaItem] = []
        with suppress(ValidationError):  # Unexpected API response
            if kind == "gameclips":
                if owner == "my":
                    response: GameclipsResponse = (
                        await self.client.gameclips.get_recent_clips_by_xuid(
                            self.client.xuid, title_id
                        )
                    )
                elif owner == "community":
                    response: GameclipsResponse = await self.client.gameclips.get_recent_community_clips_by_title_id(
                        title_id
                    )
                else:
                    return None
                items = [
                    XboxMediaItem(
                        item.user_caption
                        or dt_util.as_local(
                            dt_util.parse_datetime(item.date_recorded)
                        ).strftime("%b. %d, %Y %I:%M %p"),
                        item.thumbnails[0].uri,
                        item.game_clip_uris[0].uri,
                        MEDIA_CLASS_VIDEO,
                    )
                    for item in response.game_clips
                ]
            elif kind == "screenshots":
                if owner == "my":
                    response: ScreenshotResponse = (
                        await self.client.screenshots.get_recent_screenshots_by_xuid(
                            self.client.xuid, title_id
                        )
                    )
                elif owner == "community":
                    response: ScreenshotResponse = await self.client.screenshots.get_recent_community_screenshots_by_title_id(
                        title_id
                    )
                else:
                    return None
                items = [
                    XboxMediaItem(
                        item.user_caption
                        or dt_util.as_local(item.date_taken).strftime(
                            "%b. %d, %Y %I:%M%p"
                        ),
                        item.thumbnails[0].uri,
                        item.screenshot_uris[0].uri,
                        MEDIA_CLASS_IMAGE,
                    )
                    for item in response.screenshots
                ]

        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=f"{title}~~{category}",
            media_class=MEDIA_CLASS_DIRECTORY,
            media_content_type="",
            title=f"{owner.title()} {kind.title()}",
            can_play=False,
            can_expand=True,
            children=[_build_media_item(title, category, item) for item in items],
            children_media_class=MEDIA_CLASS_MAP[kind],
            thumbnail=thumbnail,
        )


def _build_game_item(item: InstalledPackage, images: list[Image]):
    """Build individual game."""
    thumbnail = ""
    image = _find_media_image(images.get(item.one_store_product_id, []))
    if image is not None:
        thumbnail = image.uri
        if thumbnail[0] == "/":
            thumbnail = f"https:{thumbnail}"

    return BrowseMediaSource(
        domain=DOMAIN,
        identifier=f"{item.title_id}#{item.name}#{thumbnail}",
        media_class=MEDIA_CLASS_GAME,
        media_content_type="",
        title=item.name,
        can_play=False,
        can_expand=True,
        children_media_class=MEDIA_CLASS_DIRECTORY,
        thumbnail=thumbnail,
    )


def _build_categories(title):
    """Build base categories for Xbox media."""
    _, name, thumbnail = title.split("#", 2)
    base = BrowseMediaSource(
        domain=DOMAIN,
        identifier=f"{title}",
        media_class=MEDIA_CLASS_GAME,
        media_content_type="",
        title=name,
        can_play=False,
        can_expand=True,
        children=[],
        children_media_class=MEDIA_CLASS_DIRECTORY,
        thumbnail=thumbnail,
    )

    owners = ["my", "community"]
    kinds = ["gameclips", "screenshots"]
    for owner in owners:
        for kind in kinds:
            base.children.append(
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier=f"{title}~~{owner}#{kind}",
                    media_class=MEDIA_CLASS_DIRECTORY,
                    media_content_type="",
                    title=f"{owner.title()} {kind.title()}",
                    can_play=False,
                    can_expand=True,
                    children_media_class=MEDIA_CLASS_MAP[kind],
                )
            )

    return base


def _build_media_item(title: str, category: str, item: XboxMediaItem):
    """Build individual media item."""
    kind = category.split("#", 1)[1]
    return BrowseMediaSource(
        domain=DOMAIN,
        identifier=f"{title}~~{category}~~{item.uri}",
        media_class=item.media_class,
        media_content_type=MIME_TYPE_MAP[kind],
        title=item.caption,
        can_play=True,
        can_expand=False,
        thumbnail=item.thumbnail,
    )
