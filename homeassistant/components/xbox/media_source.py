"""Xbox Media Source Implementation."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from httpx import HTTPStatusError, RequestError, TimeoutException
from pythonxbox.api.provider.titlehub.models import Image, Title, TitleFields

from homeassistant.components.media_player import BrowseError, MediaClass
from homeassistant.components.media_source import (
    BrowseMediaSource,
    MediaSource,
    MediaSourceItem,
    PlayMedia,
    Unresolvable,
)
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .binary_sensor import profile_pic
from .const import DOMAIN
from .coordinator import XboxConfigEntry
from .entity import to_https

_LOGGER = logging.getLogger(__name__)

ATTR_GAMECLIPS = "gameclips"
ATTR_SCREENSHOTS = "screenshots"
ATTR_GAME_MEDIA = "game_media"
ATTR_COMMUNITY_GAMECLIPS = "community_gameclips"
ATTR_COMMUNITY_SCREENSHOTS = "community_screenshots"

MAP_TITLE = {
    ATTR_GAMECLIPS: "Gameclips",
    ATTR_SCREENSHOTS: "Screenshots",
    ATTR_GAME_MEDIA: "Game media",
    ATTR_COMMUNITY_GAMECLIPS: "Community gameclips",
    ATTR_COMMUNITY_SCREENSHOTS: "Community screenshots",
}

MIME_TYPE_MAP = {
    ATTR_GAMECLIPS: "video/mp4",
    ATTR_COMMUNITY_GAMECLIPS: "video/mp4",
    ATTR_SCREENSHOTS: "image/png",
    ATTR_COMMUNITY_SCREENSHOTS: "image/png",
}

MEDIA_CLASS_MAP = {
    ATTR_GAMECLIPS: MediaClass.VIDEO,
    ATTR_COMMUNITY_GAMECLIPS: MediaClass.VIDEO,
    ATTR_SCREENSHOTS: MediaClass.IMAGE,
    ATTR_COMMUNITY_SCREENSHOTS: MediaClass.IMAGE,
    ATTR_GAME_MEDIA: MediaClass.IMAGE,
}

SEPARATOR = "/"


async def async_get_media_source(hass: HomeAssistant) -> XboxSource:
    """Set up Xbox media source."""

    return XboxSource(hass)


class XboxMediaSourceIdentifier:
    """Media item identifier."""

    xuid = title_id = media_type = media_id = ""

    def __init__(self, item: MediaSourceItem) -> None:
        """Initialize identifier."""
        if item.identifier is not None:
            self.xuid, _, self.title_id = (item.identifier).partition(SEPARATOR)
            self.title_id, _, self.media_type = (self.title_id).partition(SEPARATOR)
            self.media_type, _, self.media_id = (self.media_type).partition(SEPARATOR)

    def __str__(self) -> str:
        """Build identifier."""

        return SEPARATOR.join(
            [i for i in (self.xuid, self.title_id, self.media_type, self.media_id) if i]
        )


class XboxSource(MediaSource):
    """Provide Xbox screenshots and gameclips as media sources."""

    name: str = "Xbox Game Media"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize Xbox source."""
        super().__init__(DOMAIN)
        self.hass = hass

    async def async_resolve_media(self, item: MediaSourceItem) -> PlayMedia:
        """Resolve media to a url."""
        identifier = XboxMediaSourceIdentifier(item)

        if not (entries := self.hass.config_entries.async_loaded_entries(DOMAIN)):
            raise Unresolvable(
                translation_domain=DOMAIN,
                translation_key="xbox_not_configured",
            )
        try:
            entry: XboxConfigEntry = next(
                e for e in entries if e.unique_id == identifier.xuid
            )
        except StopIteration as e:
            raise Unresolvable(
                translation_domain=DOMAIN,
                translation_key="account_not_configured",
            ) from e

        client = entry.runtime_data.status.client

        if identifier.media_type in (ATTR_GAMECLIPS, ATTR_COMMUNITY_GAMECLIPS):
            try:
                if identifier.media_type == ATTR_GAMECLIPS:
                    gameclips_response = (
                        await client.gameclips.get_recent_clips_by_xuid(
                            identifier.xuid, identifier.title_id, max_items=999
                        )
                    )
                else:
                    gameclips_response = (
                        await client.gameclips.get_recent_community_clips_by_title_id(
                            identifier.title_id
                        )
                    )
            except TimeoutException as e:
                raise Unresolvable(
                    translation_domain=DOMAIN,
                    translation_key="timeout_exception",
                ) from e
            except (RequestError, HTTPStatusError) as e:
                _LOGGER.debug("Xbox exception:", exc_info=True)
                raise Unresolvable(
                    translation_domain=DOMAIN,
                    translation_key="request_exception",
                ) from e
            gameclips = gameclips_response.game_clips
            try:
                clip = next(
                    g for g in gameclips if g.game_clip_id == identifier.media_id
                )
            except StopIteration as e:
                raise Unresolvable(
                    translation_domain=DOMAIN,
                    translation_key="media_not_found",
                ) from e
            return PlayMedia(clip.game_clip_uris[0].uri, MIME_TYPE_MAP[ATTR_GAMECLIPS])

        if identifier.media_type in (ATTR_SCREENSHOTS, ATTR_COMMUNITY_SCREENSHOTS):
            try:
                if identifier.media_type == ATTR_SCREENSHOTS:
                    screenshot_response = (
                        await client.screenshots.get_recent_screenshots_by_xuid(
                            identifier.xuid, identifier.title_id, max_items=999
                        )
                    )
                else:
                    screenshot_response = await client.screenshots.get_recent_community_screenshots_by_title_id(
                        identifier.title_id
                    )
            except TimeoutException as e:
                raise Unresolvable(
                    translation_domain=DOMAIN,
                    translation_key="timeout_exception",
                ) from e
            except (RequestError, HTTPStatusError) as e:
                _LOGGER.debug("Xbox exception:", exc_info=True)
                raise Unresolvable(
                    translation_domain=DOMAIN,
                    translation_key="request_exception",
                ) from e
            screenshots = screenshot_response.screenshots
            try:
                img = next(
                    s for s in screenshots if s.screenshot_id == identifier.media_id
                )
            except StopIteration as e:
                raise Unresolvable(
                    translation_domain=DOMAIN,
                    translation_key="media_not_found",
                ) from e
            return PlayMedia(
                img.screenshot_uris[0].uri, MIME_TYPE_MAP[identifier.media_type]
            )
        if identifier.media_type == ATTR_GAME_MEDIA:
            try:
                images = (
                    (await client.titlehub.get_title_info(identifier.title_id))
                    .titles[0]
                    .images
                )
            except TimeoutException as e:
                raise Unresolvable(
                    translation_domain=DOMAIN,
                    translation_key="timeout_exception",
                ) from e
            except (RequestError, HTTPStatusError) as e:
                _LOGGER.debug("Xbox exception:", exc_info=True)
                raise Unresolvable(
                    translation_domain=DOMAIN,
                    translation_key="request_exception",
                ) from e
            if images is not None:
                try:
                    return PlayMedia(
                        images[int(identifier.media_id)].url,
                        MIME_TYPE_MAP[ATTR_SCREENSHOTS],
                    )
                except (ValueError, IndexError):
                    pass

        raise Unresolvable(
            translation_domain=DOMAIN,
            translation_key="media_not_found",
        )

    async def async_browse_media(self, item: MediaSourceItem) -> BrowseMediaSource:
        """Return media."""
        if not (entries := self.hass.config_entries.async_loaded_entries(DOMAIN)):
            raise BrowseError(
                translation_domain=DOMAIN,
                translation_key="xbox_not_configured",
            )

        # if there is only one entry we can directly jump to it
        if not item.identifier and len(entries) > 1:
            return BrowseMediaSource(
                domain=DOMAIN,
                identifier=None,
                media_class=MediaClass.DIRECTORY,
                media_content_type=MediaClass.IMAGE,
                title="Xbox Game Media",
                can_play=False,
                can_expand=True,
                children=[*await self._build_accounts(entries)],
                children_media_class=MediaClass.DIRECTORY,
            )

        identifier = XboxMediaSourceIdentifier(item)
        if not identifier.xuid and len(entries) == 1:
            if TYPE_CHECKING:
                assert entries[0].unique_id
            identifier.xuid = entries[0].unique_id

        try:
            entry: XboxConfigEntry = next(
                e for e in entries if e.unique_id == identifier.xuid
            )
        except StopIteration as e:
            raise BrowseError(
                translation_domain=DOMAIN,
                translation_key="account_not_configured",
            ) from e

        if not identifier.title_id:
            return await self._build_game_library(entry)

        if not identifier.media_type:
            return await self._build_game_title(entry, identifier)

        return await self._build_game_media(entry, identifier)

    async def _build_accounts(
        self, entries: list[XboxConfigEntry]
    ) -> list[BrowseMediaSource]:
        """List Xbox accounts."""

        return [
            BrowseMediaSource(
                domain=DOMAIN,
                identifier=entry.unique_id,
                media_class=MediaClass.DIRECTORY,
                media_content_type=MediaClass.DIRECTORY,
                title=entry.title,
                can_play=False,
                can_expand=True,
                thumbnail=gamerpic(entry),
            )
            for entry in entries
        ]

    async def _build_game_library(self, entry: XboxConfigEntry) -> BrowseMediaSource:
        """Display played games."""

        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=entry.unique_id,
            media_class=MediaClass.DIRECTORY,
            media_content_type=MediaClass.DIRECTORY,
            title=f"Xbox / {entry.title}",
            can_play=False,
            can_expand=True,
            children=[*await self._build_games(entry)],
            children_media_class=MediaClass.GAME,
        )

    async def _build_games(self, entry: XboxConfigEntry) -> list[BrowseMediaSource]:
        """List Xbox games for the selected account."""

        client = entry.runtime_data.status.client
        if TYPE_CHECKING:
            assert entry.unique_id
        fields = [
            TitleFields.ACHIEVEMENT,
            TitleFields.STATS,
            TitleFields.IMAGE,
        ]
        try:
            games = await client.titlehub.get_title_history(
                entry.unique_id, fields, max_items=999
            )
        except TimeoutException as e:
            raise BrowseError(
                translation_domain=DOMAIN,
                translation_key="timeout_exception",
            ) from e
        except (RequestError, HTTPStatusError) as e:
            _LOGGER.debug("Xbox exception:", exc_info=True)
            raise BrowseError(
                translation_domain=DOMAIN,
                translation_key="request_exception",
            ) from e

        return [
            BrowseMediaSource(
                domain=DOMAIN,
                identifier=f"{entry.unique_id}/{game.title_id}",
                media_class=MediaClass.GAME,
                media_content_type=MediaClass.GAME,
                title=game.name,
                can_play=False,
                can_expand=True,
                children_media_class=MediaClass.DIRECTORY,
                thumbnail=game_thumbnail(game.images or []),
            )
            for game in games.titles
            if game.achievement and game.achievement.source_version != 0
        ]

    async def _build_game_title(
        self, entry: XboxConfigEntry, identifier: XboxMediaSourceIdentifier
    ) -> BrowseMediaSource:
        """Display game title."""
        client = entry.runtime_data.status.client
        try:
            game = (await client.titlehub.get_title_info(identifier.title_id)).titles[0]
        except TimeoutException as e:
            raise BrowseError(
                translation_domain=DOMAIN,
                translation_key="timeout_exception",
            ) from e
        except (RequestError, HTTPStatusError) as e:
            _LOGGER.debug("Xbox exception:", exc_info=True)
            raise BrowseError(
                translation_domain=DOMAIN,
                translation_key="request_exception",
            ) from e

        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=str(identifier),
            media_class=MediaClass.GAME,
            media_content_type=MediaClass.GAME,
            title=f"Xbox / {entry.title} / {game.name}",
            can_play=False,
            can_expand=True,
            children=[*self._build_categories(identifier)],
            children_media_class=MediaClass.DIRECTORY,
        )

    def _build_categories(
        self, identifier: XboxMediaSourceIdentifier
    ) -> list[BrowseMediaSource]:
        """List media categories."""

        return [
            BrowseMediaSource(
                domain=DOMAIN,
                identifier=f"{identifier}/{media_type}",
                media_class=MediaClass.DIRECTORY,
                media_content_type=MediaClass.DIRECTORY,
                title=MAP_TITLE[media_type],
                can_play=False,
                can_expand=True,
                children_media_class=MEDIA_CLASS_MAP[media_type],
            )
            for media_type in (
                ATTR_GAMECLIPS,
                ATTR_SCREENSHOTS,
                ATTR_COMMUNITY_GAMECLIPS,
                ATTR_COMMUNITY_SCREENSHOTS,
                ATTR_GAME_MEDIA,
            )
        ]

    async def _build_game_media(
        self, entry: XboxConfigEntry, identifier: XboxMediaSourceIdentifier
    ) -> BrowseMediaSource:
        """List game media."""
        client = entry.runtime_data.status.client
        try:
            game = (await client.titlehub.get_title_info(identifier.title_id)).titles[0]
        except TimeoutException as e:
            raise BrowseError(
                translation_domain=DOMAIN,
                translation_key="timeout_exception",
            ) from e
        except (RequestError, HTTPStatusError) as e:
            _LOGGER.debug("Xbox exception:", exc_info=True)
            raise BrowseError(
                translation_domain=DOMAIN,
                translation_key="request_exception",
            ) from e

        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=str(identifier),
            media_class=MEDIA_CLASS_MAP[identifier.media_type],
            media_content_type=MediaClass.DIRECTORY,
            title=f"Xbox / {entry.title} / {game.name} / {MAP_TITLE[identifier.media_type]}",
            can_play=False,
            can_expand=True,
            children=[
                *await self._build_media_items_gameclips(entry, identifier)
                + await self._build_media_items_community_gameclips(entry, identifier)
                + await self._build_media_items_screenshots(entry, identifier)
                + await self._build_media_items_community_screenshots(entry, identifier)
                + self._build_media_items_promotional(identifier, game)
            ],
            children_media_class=MEDIA_CLASS_MAP[identifier.media_type],
        )

    async def _build_media_items_gameclips(
        self, entry: XboxConfigEntry, identifier: XboxMediaSourceIdentifier
    ) -> list[BrowseMediaSource]:
        """List media items."""
        client = entry.runtime_data.status.client

        if identifier.media_type != ATTR_GAMECLIPS:
            return []
        try:
            gameclips = (
                await client.gameclips.get_recent_clips_by_xuid(
                    identifier.xuid, identifier.title_id, max_items=999
                )
            ).game_clips
        except TimeoutException as e:
            raise BrowseError(
                translation_domain=DOMAIN,
                translation_key="timeout_exception",
            ) from e
        except (RequestError, HTTPStatusError) as e:
            _LOGGER.debug("Xbox exception:", exc_info=True)
            raise BrowseError(
                translation_domain=DOMAIN,
                translation_key="request_exception",
            ) from e

        return [
            BrowseMediaSource(
                domain=DOMAIN,
                identifier=f"{identifier}/{gameclip.game_clip_id}",
                media_class=MediaClass.VIDEO,
                media_content_type=MediaClass.VIDEO,
                title=(
                    f"{gameclip.user_caption}"
                    f"{' | ' if gameclip.user_caption else ''}"
                    f"{dt_util.get_age(gameclip.date_recorded)}"
                ),
                can_play=True,
                can_expand=False,
                thumbnail=gameclip.thumbnails[0].uri,
            )
            for gameclip in gameclips
        ]

    async def _build_media_items_community_gameclips(
        self, entry: XboxConfigEntry, identifier: XboxMediaSourceIdentifier
    ) -> list[BrowseMediaSource]:
        """List media items."""
        client = entry.runtime_data.status.client

        if identifier.media_type != ATTR_COMMUNITY_GAMECLIPS:
            return []
        try:
            gameclips = (
                await client.gameclips.get_recent_community_clips_by_title_id(
                    identifier.title_id
                )
            ).game_clips
        except TimeoutException as e:
            raise BrowseError(
                translation_domain=DOMAIN,
                translation_key="timeout_exception",
            ) from e
        except (RequestError, HTTPStatusError) as e:
            _LOGGER.debug("Xbox exception:", exc_info=True)
            raise BrowseError(
                translation_domain=DOMAIN,
                translation_key="request_exception",
            ) from e

        return [
            BrowseMediaSource(
                domain=DOMAIN,
                identifier=f"{identifier}/{gameclip.game_clip_id}",
                media_class=MediaClass.VIDEO,
                media_content_type=MediaClass.VIDEO,
                title=(
                    f"{gameclip.user_caption}"
                    f"{' | ' if gameclip.user_caption else ''}"
                    f"{dt_util.get_age(gameclip.date_recorded)}"
                ),
                can_play=True,
                can_expand=False,
                thumbnail=gameclip.thumbnails[0].uri,
            )
            for gameclip in gameclips
        ]

    async def _build_media_items_screenshots(
        self, entry: XboxConfigEntry, identifier: XboxMediaSourceIdentifier
    ) -> list[BrowseMediaSource]:
        """List media items."""
        client = entry.runtime_data.status.client

        if identifier.media_type != ATTR_SCREENSHOTS:
            return []
        try:
            screenshots = (
                await client.screenshots.get_recent_screenshots_by_xuid(
                    identifier.xuid, identifier.title_id, max_items=999
                )
            ).screenshots
        except TimeoutException as e:
            raise BrowseError(
                translation_domain=DOMAIN,
                translation_key="timeout_exception",
            ) from e
        except (RequestError, HTTPStatusError) as e:
            _LOGGER.debug("Xbox exception:", exc_info=True)
            raise BrowseError(
                translation_domain=DOMAIN,
                translation_key="request_exception",
            ) from e

        return [
            BrowseMediaSource(
                domain=DOMAIN,
                identifier=f"{identifier}/{screenshot.screenshot_id}",
                media_class=MediaClass.VIDEO,
                media_content_type=MediaClass.VIDEO,
                title=(
                    f"{screenshot.user_caption}"
                    f"{' | ' if screenshot.user_caption else ''}"
                    f"{dt_util.get_age(screenshot.date_taken)} | {screenshot.resolution_height}p"
                ),
                can_play=True,
                can_expand=False,
                thumbnail=screenshot.thumbnails[0].uri,
            )
            for screenshot in screenshots
        ]

    async def _build_media_items_community_screenshots(
        self, entry: XboxConfigEntry, identifier: XboxMediaSourceIdentifier
    ) -> list[BrowseMediaSource]:
        """List media items."""
        client = entry.runtime_data.status.client

        if identifier.media_type != ATTR_COMMUNITY_SCREENSHOTS:
            return []
        try:
            screenshots = (
                await client.screenshots.get_recent_community_screenshots_by_title_id(
                    identifier.title_id
                )
            ).screenshots
        except TimeoutException as e:
            raise BrowseError(
                translation_domain=DOMAIN,
                translation_key="timeout_exception",
            ) from e
        except (RequestError, HTTPStatusError) as e:
            _LOGGER.debug("Xbox exception:", exc_info=True)
            raise BrowseError(
                translation_domain=DOMAIN,
                translation_key="request_exception",
            ) from e

        return [
            BrowseMediaSource(
                domain=DOMAIN,
                identifier=f"{identifier}/{screenshot.screenshot_id}",
                media_class=MediaClass.VIDEO,
                media_content_type=MediaClass.VIDEO,
                title=(
                    f"{screenshot.user_caption}"
                    f"{' | ' if screenshot.user_caption else ''}"
                    f"{dt_util.get_age(screenshot.date_taken)} | {screenshot.resolution_height}p"
                ),
                can_play=True,
                can_expand=False,
                thumbnail=screenshot.thumbnails[0].uri,
            )
            for screenshot in screenshots
        ]

    def _build_media_items_promotional(
        self, identifier: XboxMediaSourceIdentifier, game: Title
    ) -> list[BrowseMediaSource]:
        """List promotional game media."""

        if identifier.media_type != ATTR_GAME_MEDIA:
            return []

        return (
            [
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier=f"{identifier}/{game.images.index(image)}",
                    media_class=MediaClass.VIDEO,
                    media_content_type=MediaClass.VIDEO,
                    title=image.type,
                    can_play=True,
                    can_expand=False,
                    thumbnail=to_https(image.url),
                )
                for image in game.images
            ]
            if game.images
            else []
        )


def gamerpic(config_entry: XboxConfigEntry) -> str | None:
    """Return gamerpic."""
    coordinator = config_entry.runtime_data.status
    if TYPE_CHECKING:
        assert config_entry.unique_id
    person = coordinator.data.presence[coordinator.client.xuid]
    return profile_pic(person)


def game_thumbnail(images: list[Image]) -> str | None:
    """Return the title image."""

    for img_type in ("BrandedKeyArt", "Poster", "BoxArt"):
        if match := next(
            (i for i in images if i.type == img_type),
            None,
        ):
            return to_https(match.url)

    return None
