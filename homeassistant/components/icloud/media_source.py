"""Expose iCloud photo albums as a media source."""

from base64 import b64decode, b64encode
from dataclasses import dataclass
import logging

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
from homeassistant.util.ssl import SSLCipherList

from .account import IcloudAccount
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


def async_setup_mediasource(hass: HomeAssistant) -> None:
    """Set up the iCloud media source."""
    hass.http.register_view(IcloudMediaSourceView(hass))


async def async_get_media_source(hass: HomeAssistant) -> "IcloudMediaSource":
    """Set up iCloud media source."""
    entries = hass.config_entries.async_entries(
        DOMAIN, include_disabled=False, include_ignore=False
    )
    if not entries:
        _LOGGER.debug("No iCloud config entries found for media source")
        raise Unresolvable("No iCloud config entries found")

    return IcloudMediaSource(hass, entries)


def _get_icloud_account(
    hass: HomeAssistant, identifier: "IcloudMediaSourceIdentifier"
) -> IcloudAccount:
    """Get iCloud account from identifier."""
    entry = hass.config_entries.async_entry_for_domain_unique_id(
        DOMAIN, identifier.config_entry_id
    )
    if entry is None or entry.runtime_data is None:
        raise Unresolvable(
            f"iCloud config entry not found: {identifier.config_entry_id}"
        )

    return entry.runtime_data


def _get_photo_album(
    icloud_account: IcloudAccount, identifier: "IcloudMediaSourceIdentifier"
) -> BasePhotoAlbum:
    """Get photo album from identifier."""
    albums: AlbumContainer | None = None
    if icloud_account.api is None:
        raise Unresolvable("iCloud account not initialized")

    if identifier.shared_album:
        albums = icloud_account.api.photos.shared_streams
    else:
        albums = icloud_account.api.photos.albums

    album = albums.get(identifier.album_id) if albums else None

    if not album:
        raise Unresolvable(f"Album not found: {identifier.album_id}")

    return album


def _get_photo_asset(
    hass: HomeAssistant, identifier: "IcloudMediaSourceIdentifier"
) -> PhotoAsset | None:
    """Get photo asset synchronously."""

    icloud_account = _get_icloud_account(hass, identifier)

    if identifier.album_id is None or identifier.photo_id is None:
        raise Unresolvable(f"Incomplete media source identifier: {identifier.photo_id}")

    album = _get_photo_album(icloud_account, identifier)

    photo: PhotoAsset | None = PHOTO_CACHE.get(identifier.photo_id)
    if photo is None:
        for item in album.photos:
            PHOTO_CACHE.set(item.id, item)
            if item.id == identifier.photo_id:
                photo = item
                break
    return photo


async def _get_media_mime_type(
    hass: HomeAssistant, identifier: "IcloudMediaSourceIdentifier"
) -> str:
    photo = await hass.async_add_executor_job(_get_photo_asset, hass, identifier)
    if photo is None:
        raise Unresolvable(f"Photo not found: {identifier.photo_id}")
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
            raise Unresolvable("Unsupported media type")


class PhotoCache:
    """Simple in-memory cache for PhotoAsset objects."""

    def __init__(self) -> None:
        """Initialize the photo cache."""
        self._cache: dict[str, PhotoAsset] = {}

    def get(self, photo_id: str) -> PhotoAsset | None:
        """Get a photo from the cache."""
        return self._cache.get(photo_id)

    def set(self, photo_id: str, photo: PhotoAsset) -> None:
        """Set a photo in the cache."""
        self._cache[photo_id] = photo


PHOTO_CACHE = PhotoCache()


@dataclass(kw_only=True)
class IcloudMediaSourceIdentifier:
    """Parse and represent an iCloud media source identifier.

    Example identifier format: config_entry_id|album/shared|album_id|photo_id
    """

    config_entry_id: str
    shared_album: bool | None = None
    album_id: str | None = None
    photo_id: str | None = None

    @staticmethod
    def from_identifier(identifier: str) -> "IcloudMediaSourceIdentifier":
        """Initialize iCloud media source identifier."""
        config_entry_id: str | None = None
        shared_album: bool | None = None
        album_id: str | None = None
        photo_id: str | None = None
        if identifier is not None:
            parts = identifier.split("|")

            for idx, part in enumerate(parts):
                if idx == 0:
                    config_entry_id = part
                elif idx == 1:
                    shared_album = part.lower() == "shared"
                elif idx == 2:
                    album_id = part
                elif idx == 3:
                    photo_id = part

        if config_entry_id is None:
            raise Unresolvable(f"Invalid media source identifier: {identifier}")

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
        return "|".join(parts)


class IcloudMediaSource(MediaSource):
    """Provide iCloud media source."""

    name = "iCloud"

    def __init__(self, hass: HomeAssistant, entries: list[ConfigEntry]) -> None:
        """Initialize iCloud media source."""
        super().__init__(DOMAIN)
        self._hass = hass
        self._entries = entries

    async def async_resolve_media(self, item: MediaSourceItem) -> PlayMedia:
        """Resolve a media item to a playable object."""
        if item.domain != DOMAIN:
            raise Unresolvable(f"Unknown media source identifier: {item.identifier}")

        identifier = IcloudMediaSourceIdentifier.from_identifier(item.identifier)
        mime_type = await _get_media_mime_type(self._hass, identifier)

        return PlayMedia(
            f"/api/icloud/media_source/serve/original/{b64encode(str(item.identifier).encode()).decode()}",
            mime_type,
        )

    async def async_browse_media(
        self,
        item: MediaSourceItem,
    ) -> BrowseMediaSource:
        """Return media."""
        if not self._hass.config_entries.async_loaded_entries(DOMAIN):
            raise BrowseError("iCloud integration not initialized")

        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=None,
            media_class=MediaClass.DIRECTORY,
            media_content_type=MediaType.ALBUM,
            title="iCloud Media",
            can_play=False,
            can_expand=True,
            children_media_class=MediaClass.DIRECTORY,
            children=[
                *await self._async_build_icloud_accounts(item),
            ],
        )

    async def _async_build_icloud_accounts(
        self,
        item: MediaSourceItem,
    ) -> list[BrowseMediaSource]:
        """Handle browsing of different iCloud accounts."""
        if not item.identifier:
            return [
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
                for entry in self._entries
                if entry.unique_id is not None
            ]

        identifier = IcloudMediaSourceIdentifier.from_identifier(item.identifier)
        icloud_account = _get_icloud_account(self._hass, identifier)

        if identifier.shared_album is None:
            return [
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
            ]

        if identifier.album_id is None:

            def browse_albums() -> list[BrowseMediaSource]:
                """Browse albums synchronously."""
                # Browse albums
                albums: AlbumContainer | None = None
                if icloud_account.api is None:
                    raise Unresolvable("iCloud account not initialized")

                if identifier.shared_album:
                    albums = icloud_account.api.photos.shared_streams
                else:
                    albums = icloud_account.api.photos.albums

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

            return await self._hass.async_add_executor_job(browse_albums)

        if identifier.photo_id is None:
            # Browse photos in album
            album = await self._hass.async_add_executor_job(
                _get_photo_album, icloud_account, identifier
            )

            photos_list = await self._hass.async_add_executor_job(list, album.photos)
            return self._get_photo_list(identifier, photos_list)

        raise Unresolvable(f"Unknown media item '{item.identifier}' during browsing.")

    def _get_photo_list(self, identifier, photos):
        """Get list of photos synchronously."""
        for photo in photos:
            PHOTO_CACHE.set(photo.id, photo)
            photo_id = IcloudMediaSourceIdentifier(
                config_entry_id=identifier.config_entry_id,
                shared_album=identifier.shared_album,
                album_id=identifier.album_id,
                photo_id=photo.id,
            )

            if photo.item_type == "image":
                media_class = MediaClass.IMAGE
            else:
                media_class = MediaClass.VIDEO

            item = BrowseMediaSource(
                domain=DOMAIN,
                identifier=str(photo_id),
                media_class=media_class,
                media_content_type="",
                can_play=True,
                can_expand=False,
                title=photo.filename,
                thumbnail=f"/api/icloud/media_source/serve/thumb/{b64encode(str(photo_id).encode()).decode()}",
            )
            yield item


class IcloudMediaSourceView(HomeAssistantView):
    """Handle media serving via HTTP view."""

    url = "/api/icloud/media_source/serve/{version}/{image_id}"
    name = "api:icloud:media_source:serve"
    requires_auth = True

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize iCloud media source view."""
        super().__init__()
        self._hass = hass
        self.session = async_get_clientsession(
            hass,
            verify_ssl=False,
            ssl_cipher=SSLCipherList.INSECURE,
        )

    async def get(
        self,
        request: web.Request,
        version: str,
        image_id: str,
    ) -> web.StreamResponse:
        """Get the image from iCloud."""

        identifier = IcloudMediaSourceIdentifier.from_identifier(
            b64decode(image_id).decode()
        )

        photo = await self._hass.async_add_executor_job(
            _get_photo_asset, self._hass, identifier
        )

        if photo is None:
            raise web.HTTPNotFound

        url = photo.versions[version]["url"]
        icloud_response = await self.session.get(
            url,
            timeout=ClientTimeout(connect=15, sock_connect=15, sock_read=5, total=None),
        )

        response_headers = dict(icloud_response.headers)
        response_headers.update(CACHE_HEADERS)
        response_headers[hdrs.CONTENT_DISPOSITION] = (
            f'attachment;filename="{photo.filename}"'
        )
        response_headers[hdrs.CONTENT_TYPE] = icloud_response.headers.get(
            hdrs.CONTENT_TYPE, "application/octet-stream"
        )
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
