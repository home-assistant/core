"""Expose iCloud photo albums as a media source."""

from base64 import b64decode, b64encode
import binascii
from collections import OrderedDict
from dataclasses import dataclass
import logging
import threading
import urllib.parse

from aiohttp import ClientTimeout, hdrs, web
from pyicloud.services.photos import (
    AlbumContainer,
    BasePhotoAlbum,
    PhotoAlbumFolder,
    PhotoAsset,
)

from homeassistant.components.http import HomeAssistantView
from homeassistant.components.http.static import CACHE_HEADERS
from homeassistant.components.media_player import BrowseError, MediaClass, MediaType
from homeassistant.components.media_source import (
    BrowseMediaSource,
    MediaSource,
    MediaSourceItem,
    PlayMedia,
    Unresolvable,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .account import IcloudAccount
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

MAX_PHOTO_CACHE_SIZE = 1000


def async_setup_mediasource(hass: HomeAssistant) -> None:
    """Set up the iCloud media source."""
    hass.http.register_view(IcloudMediaSourceView(hass))


async def async_get_media_source(hass: HomeAssistant) -> IcloudMediaSource:
    """Set up iCloud media source."""
    return IcloudMediaSource(hass)


def _get_icloud_account_and_title(
    hass: HomeAssistant, identifier: IcloudMediaSourceIdentifier
) -> tuple[IcloudAccount, str]:
    """Get iCloud account from identifier. Also return the account title for display purposes."""
    entry = hass.config_entries.async_entry_for_domain_unique_id(
        DOMAIN, identifier.config_entry_id
    )
    if entry is None:
        raise Unresolvable(
            translation_domain=DOMAIN,
            translation_key="config_entry_not_found",
            translation_placeholders={"entry": identifier.config_entry_id},
        )
    if getattr(entry, "runtime_data", None) is None:
        raise Unresolvable(
            translation_domain=DOMAIN,
            translation_key="account_not_initialized",
            translation_placeholders={"entry": identifier.config_entry_id},
        )

    return entry.runtime_data, entry.title


async def _get_photo_library(
    hass: HomeAssistant,
    icloud_account: IcloudAccount,
    identifier: IcloudMediaSourceIdentifier,
) -> AlbumContainer:
    """Get photo library."""

    def get_photo_library_sync() -> AlbumContainer:
        """Get photo library synchronously."""
        if icloud_account.api is None or icloud_account.api.photos is None:
            raise Unresolvable(
                translation_domain=DOMAIN,
                translation_key="account_not_initialized",
                translation_placeholders={"entry": identifier.config_entry_id},
            )
        return (
            icloud_account.api.photos.shared_streams
            if identifier.shared_album is True
            else icloud_account.api.photos.albums
        )

    return await hass.async_add_executor_job(get_photo_library_sync)


async def _get_photo_album(
    hass: HomeAssistant,
    icloud_account: IcloudAccount,
    identifier: IcloudMediaSourceIdentifier,
) -> BasePhotoAlbum:
    """Get photo album from identifier."""

    def _find_album_sync() -> BasePhotoAlbum | None:
        """Find album synchronously."""
        album: BasePhotoAlbum | None = (
            albums.get(identifier.album_id) if albums and identifier.album_id else None
        )
        if not album:
            raise Unresolvable(
                translation_domain=DOMAIN,
                translation_key="album_not_found",
            )
        return album

    albums: AlbumContainer | None = None
    if icloud_account.api is None:
        raise Unresolvable(
            translation_domain=DOMAIN,
            translation_key="account_not_initialized",
            translation_placeholders={"entry": identifier.config_entry_id},
        )

    albums = await _get_photo_library(hass, icloud_account, identifier)

    return await hass.async_add_executor_job(_find_album_sync)


async def _get_photo_asset(
    hass: HomeAssistant, identifier: IcloudMediaSourceIdentifier
) -> PhotoAsset:
    """Get photo asset asynchronously."""

    def _get_photo_asset_sync(album: BasePhotoAlbum) -> PhotoAsset | None:
        """Get photo asset synchronously."""
        for item in album.photos:
            if item.id == identifier.photo_id:
                return item
        return None

    icloud_account, _ = _get_icloud_account_and_title(hass, identifier)

    if identifier.album_id is None or identifier.photo_id is None:
        raise Unresolvable(
            translation_domain=DOMAIN,
            translation_key="incomplete_media_source_identifier",
        )

    photo: PhotoAsset | None = PhotoCache.instance(icloud_account).get(
        identifier.photo_id
    )
    if photo is None:
        album: BasePhotoAlbum = await _get_photo_album(hass, icloud_account, identifier)
        photo = await hass.async_add_executor_job(_get_photo_asset_sync, album)
        PhotoCache.instance(icloud_account).set(identifier.photo_id, photo)
    if photo is None:
        raise Unresolvable(
            translation_domain=DOMAIN,
            translation_key="photo_not_found",
        )
    return photo


async def _get_media_mime_type(
    hass: HomeAssistant, identifier: IcloudMediaSourceIdentifier
) -> str:
    """Get media MIME type asynchronously."""
    photo: PhotoAsset = await _get_photo_asset(hass, identifier)

    match photo.item_type:
        case "image":
            if photo.filename.lower().endswith(".png"):
                return "image/png"
            if photo.filename.lower().endswith(".heic"):
                return "image/heic"
            return "image/jpeg"
        case "movie":
            return "video/mp4"
        case _:
            raise Unresolvable(
                translation_domain=DOMAIN,
                translation_key="unsupported_media_type",
            )


class PhotoCache:
    """Simple in-memory cache for PhotoAsset objects."""

    @classmethod
    def instance(cls, icloud_account: IcloudAccount) -> PhotoCache:
        """Get the singleton instance of the photo cache."""

        if icloud_account.photo_cache is None:
            icloud_account.photo_cache = cls()
        return icloud_account.photo_cache

    def __init__(self, max_size: int = MAX_PHOTO_CACHE_SIZE) -> None:
        """Initialize the photo cache."""
        self._cache: OrderedDict[str, PhotoAsset] = OrderedDict()
        self._max_size = max_size
        self._lock = threading.RLock()

    def get(self, photo_id: str) -> PhotoAsset | None:
        """Get a photo from the cache."""
        with self._lock:
            photo = self._cache.get(photo_id)
            if photo is not None:
                # Move the accessed item to the end to show that it was recently used
                self._cache.move_to_end(photo_id)
            return photo

    def set(self, photo_id: str, photo: PhotoAsset) -> None:
        """Set a photo in the cache."""
        with self._lock:
            self._cache[photo_id] = photo
            if len(self._cache) > self._max_size:
                self._cache.popitem(last=False)


@dataclass(kw_only=True)
class IcloudMediaSourceIdentifier:
    """Parse and represent an iCloud media source identifier.

    Example identifier format: config_entry_id/album/album_id
    Example identifier format: config_entry_id/shared/shared_album_id
    Example identifier format: config_entry_id/album/album_id/photo_id
    Example identifier format: config_entry_id/shared/shared_album_id/photo_id

    """

    config_entry_id: str
    shared_album: bool | None = None
    album_id: str | None = None
    photo_id: str | None = None

    @staticmethod
    def from_identifier(identifier: str) -> IcloudMediaSourceIdentifier:
        """Initialize iCloud media source identifier."""
        config_entry_id: str = ""
        shared_album: bool | None = None
        album_id: str | None = None
        photo_id: str | None = None
        parts: list[str] = identifier.split("/") if identifier else []

        for idx, part in enumerate(parts):
            if idx == 0:
                config_entry_id = part
            elif idx == 1:
                if part.lower() not in ("shared", "album"):
                    raise Unresolvable(
                        translation_domain=DOMAIN,
                        translation_key="invalid_view_type",
                    )
                shared_album = part.lower() == "shared"
            elif idx == 2:
                album_id = part
            elif idx == 3:
                photo_id = part

        if not config_entry_id:
            raise Unresolvable(
                translation_domain=DOMAIN,
                translation_key="incomplete_media_source_identifier",
            )

        return IcloudMediaSourceIdentifier(
            config_entry_id=config_entry_id,
            shared_album=shared_album,
            album_id=album_id,
            photo_id=photo_id,
        )

    def __str__(self) -> str:
        """Return string representation of the identifier."""
        parts = [self.config_entry_id]
        if self.shared_album is not None:
            parts.append("shared" if self.shared_album else "album")
        if self.album_id is not None:
            parts.append(self.album_id)
        if self.photo_id is not None:
            parts.append(self.photo_id)
        return "/".join(parts)


class IcloudMediaSource(MediaSource):
    """Provide iCloud media source."""

    name = "iCloud"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize iCloud media source."""
        super().__init__(DOMAIN)
        self._hass = hass

    async def async_resolve_media(self, item: MediaSourceItem) -> PlayMedia:
        """Resolve a media item to a playable object."""
        if not self._hass.config_entries.async_loaded_entries(DOMAIN):
            raise BrowseError(
                translation_domain=DOMAIN,
                translation_key="config_entry_not_loaded",
            )

        identifier = IcloudMediaSourceIdentifier.from_identifier(item.identifier)
        mime_type = await _get_media_mime_type(self._hass, identifier)

        return PlayMedia(
            f"/api/icloud/media_source/serve/original/{b64encode(str(item.identifier).encode()).decode()}",
            mime_type,
        )

    def _get_config_entries(self) -> list[ConfigEntry]:
        """Get iCloud config entries."""
        return self._hass.config_entries.async_entries(
            DOMAIN, include_disabled=False, include_ignore=False
        )

    async def _build_title_for_identifier(
        self,
        identifier: IcloudMediaSourceIdentifier | None,
    ) -> str:
        """Build title for media source identifier."""
        title_parts = ["iCloud Media"]

        if identifier and identifier.config_entry_id is not None:
            icloud_account, title = _get_icloud_account_and_title(
                self._hass, identifier
            )
            title_parts.append(title)

        if identifier and identifier.shared_album is True:
            title_parts.append("Shared Streams")
        elif identifier and identifier.shared_album is False:
            title_parts.append("Albums")

        if identifier and identifier.album_id is not None:
            album = await _get_photo_album(self._hass, icloud_account, identifier)
            title_parts.append(album.title)

        return " / ".join(title_parts)

    async def async_browse_media(
        self,
        item: MediaSourceItem,
    ) -> BrowseMediaSource:
        """Return media."""
        if not self._hass.config_entries.async_loaded_entries(DOMAIN):
            raise BrowseError(
                translation_domain=DOMAIN,
                translation_key="config_entry_not_loaded",
            )

        if not item.identifier:
            return await self._async_build_icloud_accounts()

        identifier = IcloudMediaSourceIdentifier.from_identifier(item.identifier)

        if identifier.shared_album is None:
            return await self._async_build_album_types(identifier)

        icloud_account, _ = _get_icloud_account_and_title(self._hass, identifier)

        if identifier.album_id is None:
            return await self._async_build_albums(identifier, icloud_account)

        if identifier.photo_id is None:
            return await self._async_build_photos(identifier, icloud_account)

        raise BrowseError(
            translation_domain=DOMAIN,
            translation_key="unknown_media_item",
        )

    async def _async_build_icloud_accounts(
        self,
    ) -> BrowseMediaSource:
        """Handle browsing of different iCloud accounts."""
        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=None,
            media_class=MediaClass.DIRECTORY,
            media_content_type=MediaType.ALBUM,
            title=await self._build_title_for_identifier(None),
            can_play=False,
            can_expand=True,
            children_media_class=MediaClass.DIRECTORY,
            children=[
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier=str(
                        IcloudMediaSourceIdentifier(config_entry_id=entry.unique_id)
                    ),
                    media_class=MediaClass.DIRECTORY,
                    media_content_type=MediaType.ALBUM,
                    title=entry.title,
                    can_play=False,
                    can_expand=True,
                )
                for entry in self._get_config_entries()
                if entry.unique_id is not None
            ],
        )

    async def _async_build_album_types(
        self,
        identifier: IcloudMediaSourceIdentifier,
    ) -> BrowseMediaSource:
        """Handle browsing of album types (albums vs shared albums)."""
        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=None,
            media_class=MediaClass.DIRECTORY,
            media_content_type=MediaType.ALBUM,
            title=await self._build_title_for_identifier(identifier),
            can_play=False,
            can_expand=True,
            children_media_class=MediaClass.DIRECTORY,
            children=[
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier=str(
                        IcloudMediaSourceIdentifier(
                            config_entry_id=identifier.config_entry_id,
                            shared_album=False,
                        )
                    ),
                    media_class=MediaClass.DIRECTORY,
                    media_content_type=MediaType.ALBUM,
                    can_play=False,
                    can_expand=True,
                    title="Albums",
                ),
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier=str(
                        IcloudMediaSourceIdentifier(
                            config_entry_id=identifier.config_entry_id,
                            shared_album=True,
                        )
                    ),
                    media_class=MediaClass.DIRECTORY,
                    media_content_type=MediaType.ALBUM,
                    can_play=False,
                    can_expand=True,
                    title="Shared Streams",
                ),
            ],
        )

    async def _async_build_albums(
        self,
        identifier: IcloudMediaSourceIdentifier,
        icloud_account: IcloudAccount,
    ) -> BrowseMediaSource:
        """Handle browsing of albums."""
        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=None,
            media_class=MediaClass.DIRECTORY,
            media_content_type=MediaType.ALBUM,
            title=await self._build_title_for_identifier(identifier),
            can_play=False,
            can_expand=True,
            children_media_class=MediaClass.DIRECTORY,
            children=await self._browse_albums(identifier, icloud_account),
        )

    async def _async_build_photos(
        self,
        identifier: IcloudMediaSourceIdentifier,
        icloud_account: IcloudAccount,
    ) -> BrowseMediaSource:
        """Handle browsing of photos in an album."""

        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=None,
            media_class=MediaClass.DIRECTORY,
            media_content_type=MediaType.ALBUM,
            title=await self._build_title_for_identifier(identifier),
            can_play=False,
            can_expand=True,
            children_media_class=MediaClass.DIRECTORY,
            children=await self._get_photo_list(identifier, icloud_account),
        )

    async def _browse_albums(
        self,
        identifier: IcloudMediaSourceIdentifier,
        icloud_account: IcloudAccount,
    ) -> list[BrowseMediaSource]:
        """Browse albums asynchronously."""

        albums: AlbumContainer | None = None
        if icloud_account.api is None:
            raise BrowseError(
                translation_domain=DOMAIN,
                translation_key="account_not_initialized",
                translation_placeholders={"entry": identifier.config_entry_id},
            )

        albums = await _get_photo_library(self._hass, icloud_account, identifier)

        children: list[BrowseMediaSource] = []
        if albums is not None:
            for album in albums:
                if isinstance(album, PhotoAlbumFolder):
                    continue
                children.append(
                    BrowseMediaSource(
                        domain=DOMAIN,
                        identifier=str(
                            IcloudMediaSourceIdentifier(
                                config_entry_id=identifier.config_entry_id,
                                shared_album=identifier.shared_album,
                                album_id=album.id,
                            )
                        ),
                        media_class=MediaClass.DIRECTORY,
                        media_content_type=MediaType.ALBUM,
                        can_play=False,
                        can_expand=True,
                        title=album.title,
                    )
                )
        return children

    async def _get_photo_list(
        self,
        identifier: IcloudMediaSourceIdentifier,
        icloud_account: IcloudAccount,
    ) -> list[BrowseMediaSource]:
        """Get list of photos asynchronously."""

        def _get_photo_list_sync(album: BasePhotoAlbum) -> list[BrowseMediaSource]:
            """Get list of photos synchronously."""
            items: list[BrowseMediaSource] = []
            for photo in album.photos:
                PhotoCache.instance(icloud_account).set(photo.id, photo)
                photo_id = IcloudMediaSourceIdentifier(
                    config_entry_id=identifier.config_entry_id,
                    shared_album=identifier.shared_album,
                    album_id=identifier.album_id,
                    photo_id=photo.id,
                )

                item = BrowseMediaSource(
                    domain=DOMAIN,
                    identifier=str(photo_id),
                    media_class=(
                        MediaClass.IMAGE
                        if photo.item_type == "image"
                        else MediaClass.VIDEO
                    ),
                    media_content_type=(
                        MediaType.IMAGE
                        if photo.item_type == "image"
                        else MediaType.VIDEO
                    ),
                    can_play=True,
                    can_expand=False,
                    title=photo.filename,
                    thumbnail=f"/api/icloud/media_source/serve/thumb{'' if photo.item_type == 'image' else '_image'}/{b64encode(str(photo_id).encode()).decode()}",
                )
                items.append(item)
            return items

        album: BasePhotoAlbum = await _get_photo_album(
            self._hass, icloud_account, identifier
        )
        return await self._hass.async_add_executor_job(_get_photo_list_sync, album)


class IcloudMediaSourceView(HomeAssistantView):
    """Handle media serving via HTTP view."""

    url = "/api/icloud/media_source/serve/{version}/{image_id}"
    name = "api:icloud:media_source:serve"
    requires_auth = True

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize iCloud media source view."""
        super().__init__()
        self._hass = hass
        self.session = async_get_clientsession(hass)

    async def get(
        self,
        request: web.Request,
        version: str,
        image_id: str,
    ) -> web.StreamResponse:
        """Get the image from iCloud."""

        try:
            identifier = IcloudMediaSourceIdentifier.from_identifier(
                b64decode(image_id, validate=True).decode()
            )
        except (Unresolvable, binascii.Error, UnicodeDecodeError) as err:
            _LOGGER.error("Error decoding iCloud media source identifier: %s", err)
            raise web.HTTPBadRequest from err

        photo = await _get_photo_asset(self._hass, identifier)

        url = photo.versions.get(version, {}).get("url")
        if url is None and version.startswith("thumb"):
            # try the medium version for thumbnails if the requested version is not available, as some videos only have a medium version and no separate thumbnail version
            url = photo.versions.get(version.replace("thumb", "medium"), {}).get("url")
        if url is None:
            raise web.HTTPNotFound

        request_headers = {}
        if hdrs.RANGE in request.headers:
            request_headers[hdrs.RANGE] = request.headers[hdrs.RANGE]

        icloud_response = await self.session.get(
            url,
            timeout=ClientTimeout(
                connect=15, sock_connect=15, sock_read=30, total=None
            ),
            headers=request_headers,
        )

        response_headers: dict[str, str] = {}
        response_headers.update(CACHE_HEADERS)
        response_headers[hdrs.CONTENT_DISPOSITION] = (
            f'attachment;filename="{urllib.parse.quote(photo.filename, safe="")}"'
        )

        for header in (
            hdrs.CONTENT_TYPE,
            hdrs.LAST_MODIFIED,
            hdrs.ACCEPT_RANGES,
            hdrs.CONTENT_RANGE,
        ):
            if header in icloud_response.headers:
                response_headers[header] = icloud_response.headers[header]

        response = web.StreamResponse(
            status=icloud_response.status,
            reason=icloud_response.reason,
            headers=response_headers,
        )
        await response.prepare(request)

        try:
            async for chunk in icloud_response.content.iter_chunked(65536):
                await response.write(chunk)
        except TimeoutError:
            _LOGGER.debug(
                "Timeout while reading iCloud, writing EOF",
            )
        finally:
            icloud_response.release()

        await response.write_eof()
        return response
