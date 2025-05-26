"""Immich as a media source."""

from __future__ import annotations

from logging import getLogger
import mimetypes

from aiohttp.web import HTTPNotFound, Request, Response, StreamResponse
from aioimmich.exceptions import ImmichError

from homeassistant.components.http import HomeAssistantView
from homeassistant.components.media_player import MediaClass
from homeassistant.components.media_source import (
    BrowseError,
    BrowseMediaSource,
    MediaSource,
    MediaSourceItem,
    PlayMedia,
    Unresolvable,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import ChunkAsyncStreamIterator

from .const import DOMAIN
from .coordinator import ImmichConfigEntry

LOGGER = getLogger(__name__)


async def async_get_media_source(hass: HomeAssistant) -> MediaSource:
    """Set up Immich media source."""
    entries = hass.config_entries.async_entries(
        DOMAIN, include_disabled=False, include_ignore=False
    )
    hass.http.register_view(ImmichMediaView(hass))
    return ImmichMediaSource(hass, entries)


class ImmichMediaSourceIdentifier:
    """Immich media item identifier."""

    def __init__(self, identifier: str) -> None:
        """Split identifier into parts."""
        parts = identifier.split("/")
        # coonfig_entry.unique_id/album_id/asset_it/filename
        self.unique_id = parts[0]
        self.album_id = parts[1] if len(parts) > 1 else None
        self.asset_id = parts[2] if len(parts) > 2 else None
        self.file_name = parts[3] if len(parts) > 2 else None


class ImmichMediaSource(MediaSource):
    """Provide Immich as media sources."""

    name = "Immich"

    def __init__(self, hass: HomeAssistant, entries: list[ConfigEntry]) -> None:
        """Initialize Immich media source."""
        super().__init__(DOMAIN)
        self.hass = hass
        self.entries = entries

    async def async_browse_media(
        self,
        item: MediaSourceItem,
    ) -> BrowseMediaSource:
        """Return media."""
        if not self.hass.config_entries.async_loaded_entries(DOMAIN):
            raise BrowseError("Immich is not configured")
        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=None,
            media_class=MediaClass.DIRECTORY,
            media_content_type=MediaClass.IMAGE,
            title="Immich",
            can_play=False,
            can_expand=True,
            children_media_class=MediaClass.DIRECTORY,
            children=[
                *await self._async_build_immich(item),
            ],
        )

    async def _async_build_immich(
        self, item: MediaSourceItem
    ) -> list[BrowseMediaSource]:
        """Handle browsing different immich instances."""
        if not item.identifier:
            return [
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier=entry.unique_id,
                    media_class=MediaClass.DIRECTORY,
                    media_content_type=MediaClass.IMAGE,
                    title=entry.title,
                    can_play=False,
                    can_expand=True,
                )
                for entry in self.entries
            ]
        identifier = ImmichMediaSourceIdentifier(item.identifier)
        entry: ImmichConfigEntry | None = (
            self.hass.config_entries.async_entry_for_domain_unique_id(
                DOMAIN, identifier.unique_id
            )
        )
        assert entry
        immich_api = entry.runtime_data.api

        if identifier.album_id is None:
            # Get Albums
            try:
                albums = await immich_api.albums.async_get_all_albums()
            except ImmichError:
                return []

            return [
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier=f"{item.identifier}/{album.album_id}",
                    media_class=MediaClass.DIRECTORY,
                    media_content_type=MediaClass.IMAGE,
                    title=album.name,
                    can_play=False,
                    can_expand=True,
                    thumbnail=f"/immich/{identifier.unique_id}/{album.thumbnail_asset_id}/thumb.jpg/thumbnail",
                )
                for album in albums
            ]

        # Request items of album
        try:
            album_info = await immich_api.albums.async_get_album_info(
                identifier.album_id
            )
        except ImmichError:
            return []

        ret = [
            BrowseMediaSource(
                domain=DOMAIN,
                identifier=(
                    f"{identifier.unique_id}/"
                    f"{identifier.album_id}/"
                    f"{asset.asset_id}/"
                    f"{asset.file_name}"
                ),
                media_class=MediaClass.IMAGE,
                media_content_type=asset.mime_type,
                title=asset.file_name,
                can_play=False,
                can_expand=False,
                thumbnail=f"/immich/{identifier.unique_id}/{asset.asset_id}/{asset.file_name}/thumbnail",
            )
            for asset in album_info.assets
            if asset.mime_type.startswith("image/")
        ]

        ret.extend(
            BrowseMediaSource(
                domain=DOMAIN,
                identifier=(
                    f"{identifier.unique_id}/"
                    f"{identifier.album_id}/"
                    f"{asset.asset_id}/"
                    f"{asset.file_name}"
                ),
                media_class=MediaClass.VIDEO,
                media_content_type=asset.mime_type,
                title=asset.file_name,
                can_play=True,
                can_expand=False,
                thumbnail=f"/immich/{identifier.unique_id}/{asset.asset_id}/thumbnail.jpg/thumbnail",
            )
            for asset in album_info.assets
            if asset.mime_type.startswith("video/")
        )

        return ret

    async def async_resolve_media(self, item: MediaSourceItem) -> PlayMedia:
        """Resolve media to a url."""
        identifier = ImmichMediaSourceIdentifier(item.identifier)
        if identifier.file_name is None:
            raise Unresolvable("No file name")
        mime_type, _ = mimetypes.guess_type(identifier.file_name)
        if not isinstance(mime_type, str):
            raise Unresolvable("No file extension")
        return PlayMedia(
            (
                f"/immich/{identifier.unique_id}/{identifier.asset_id}/{identifier.file_name}/fullsize"
            ),
            mime_type,
        )


class ImmichMediaView(HomeAssistantView):
    """Immich Media Finder View."""

    url = "/immich/{source_dir_id}/{location:.*}"
    name = "immich"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the media view."""
        self.hass = hass

    async def get(
        self, request: Request, source_dir_id: str, location: str
    ) -> Response | StreamResponse:
        """Start a GET request."""
        if not self.hass.config_entries.async_loaded_entries(DOMAIN):
            raise HTTPNotFound

        asset_id, file_name, size = location.split("/")
        mime_type, _ = mimetypes.guess_type(file_name)
        if not isinstance(mime_type, str):
            raise HTTPNotFound

        entry: ImmichConfigEntry | None = (
            self.hass.config_entries.async_entry_for_domain_unique_id(
                DOMAIN, source_dir_id
            )
        )
        assert entry
        immich_api = entry.runtime_data.api

        # stream response for videos
        if mime_type.startswith("video/"):
            try:
                resp = await immich_api.assets.async_play_video_stream(asset_id)
            except ImmichError as exc:
                raise HTTPNotFound from exc
            stream = ChunkAsyncStreamIterator(resp)
            response = StreamResponse()
            await response.prepare(request)
            async for chunk in stream:
                await response.write(chunk)
            return response

        # web response for images
        try:
            image = await immich_api.assets.async_view_asset(asset_id, size)
        except ImmichError as exc:
            raise HTTPNotFound from exc
        return Response(body=image, content_type=mime_type)
