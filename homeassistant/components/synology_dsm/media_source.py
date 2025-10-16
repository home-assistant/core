"""Expose Synology DSM as a media source."""

from __future__ import annotations

from logging import getLogger
import mimetypes
import re
from typing import TYPE_CHECKING

from aiohttp import web
from aiohttp.streams import StreamReader
from synology_dsm.api.photos.model import SynoPhotosAlbum, SynoPhotosItem
from synology_dsm.exceptions import SynologyDSMException

from homeassistant.components import http
from homeassistant.components.media_player import BrowseError, MediaClass
from homeassistant.components.media_source import (
    BrowseMediaSource,
    MediaSource,
    MediaSourceItem,
    PlayMedia,
    Unresolvable,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, SHARED_SUFFIX
from .coordinator import SynologyDSMConfigEntry, SynologyDSMData

LOGGER = getLogger(__name__)


async def async_get_media_source(hass: HomeAssistant) -> MediaSource:
    """Set up Synology media source."""
    entries = hass.config_entries.async_entries(
        DOMAIN, include_disabled=False, include_ignore=False
    )
    hass.http.register_view(SynologyDsmMediaView(hass))
    return SynologyPhotosMediaSource(hass, entries)


class SynologyPhotosMediaSourceIdentifier:
    """Synology Photos item identifier."""

    def __init__(self, identifier: str) -> None:
        """Split identifier into parts."""
        parts = identifier.split("/")

        self.unique_id = parts[0]
        self.album_id = None
        self.cache_key = None
        self.file_name = None
        self.is_shared = False
        self.passphrase = ""

        if len(parts) > 1:
            album_parts = parts[1].split("_")
            self.album_id = album_parts[0]
            if len(album_parts) > 1:
                self.passphrase = parts[1].replace(f"{self.album_id}_", "")

        if len(parts) > 2:
            self.cache_key = parts[2]

        if len(parts) > 3:
            self.file_name = parts[3]
            if self.file_name.endswith(SHARED_SUFFIX):
                self.is_shared = True
                self.file_name = self.file_name.removesuffix(SHARED_SUFFIX)


class SynologyPhotosMediaSource(MediaSource):
    """Provide Synology Photos as media sources."""

    name = "Synology Photos"

    def __init__(self, hass: HomeAssistant, entries: list[ConfigEntry]) -> None:
        """Initialize Synology source."""
        super().__init__(DOMAIN)
        self.hass = hass
        self.entries = entries

    async def async_browse_media(
        self,
        item: MediaSourceItem,
    ) -> BrowseMediaSource:
        """Return media."""
        if not self.hass.config_entries.async_loaded_entries(DOMAIN):
            raise BrowseError("Diskstation not initialized")
        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=None,
            media_class=MediaClass.DIRECTORY,
            media_content_type=MediaClass.DIRECTORY,
            title="Synology Photos",
            can_play=False,
            can_expand=True,
            children_media_class=MediaClass.DIRECTORY,
            children=[
                *await self._async_build_diskstations(item),
            ],
        )

    async def _async_build_diskstations(
        self, item: MediaSourceItem
    ) -> list[BrowseMediaSource]:
        """Handle browsing different diskstations."""
        if not item.identifier:
            return [
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier=entry.unique_id,
                    media_class=MediaClass.DIRECTORY,
                    media_content_type=MediaClass.DIRECTORY,
                    title=f"{entry.title} - {entry.unique_id}",
                    can_play=False,
                    can_expand=True,
                )
                for entry in self.entries
            ]
        identifier = SynologyPhotosMediaSourceIdentifier(item.identifier)
        entry: SynologyDSMConfigEntry | None = (
            self.hass.config_entries.async_entry_for_domain_unique_id(
                DOMAIN, identifier.unique_id
            )
        )
        if TYPE_CHECKING:
            assert entry
        diskstation = entry.runtime_data
        if TYPE_CHECKING:
            assert diskstation.api.photos is not None

        if identifier.album_id is None:
            # Get Albums
            try:
                albums = await diskstation.api.photos.get_albums()
            except SynologyDSMException:
                return []
            if TYPE_CHECKING:
                assert albums is not None

            ret = [
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier=f"{item.identifier}/0",
                    media_class=MediaClass.DIRECTORY,
                    media_content_type=MediaClass.DIRECTORY,
                    title="All media",
                    can_play=False,
                    can_expand=True,
                )
            ]
            ret += [
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier=f"{item.identifier}/shared",
                    media_class=MediaClass.DIRECTORY,
                    media_content_type=MediaClass.DIRECTORY,
                    title="Shared space",
                    can_play=False,
                    can_expand=True,
                )
            ]
            ret.extend(
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier=f"{item.identifier}/{album.album_id}_{album.passphrase}",
                    media_class=MediaClass.DIRECTORY,
                    media_content_type=MediaClass.DIRECTORY,
                    title=album.name,
                    can_play=False,
                    can_expand=True,
                )
                for album in albums
            )

            return ret

        # Request items of album
        # Get Items
        if identifier.album_id == "shared":
            # Get items from shared space
            try:
                album_items = await diskstation.api.photos.get_items_from_shared_space(
                    0, 1000
                )
            except SynologyDSMException:
                return []
        else:
            album = SynoPhotosAlbum(
                int(identifier.album_id), "", 0, identifier.passphrase
            )
            try:
                album_items = await diskstation.api.photos.get_items_from_album(
                    album, 0, 1000
                )
            except SynologyDSMException:
                return []
        if TYPE_CHECKING:
            assert album_items is not None

        ret = []
        for album_item in album_items:
            mime_type, _ = mimetypes.guess_type(album_item.file_name)
            if isinstance(mime_type, str) and mime_type.startswith(
                ("image/", "video/")
            ):
                # Force small small thumbnails
                album_item.thumbnail_size = "sm"
                suffix = ""
                if album_item.is_shared:
                    suffix = SHARED_SUFFIX

                # Determine media class based on MIME type
                media_class = (
                    MediaClass.MOVIE
                    if mime_type.startswith("video/")
                    else MediaClass.IMAGE
                )

                ret.append(
                    BrowseMediaSource(
                        domain=DOMAIN,
                        identifier=(
                            f"{identifier.unique_id}/"
                            f"{identifier.album_id}_{identifier.passphrase}/"
                            f"{album_item.thumbnail_cache_key}/"
                            f"{album_item.file_name}{suffix}"
                        ),
                        media_class=media_class,
                        media_content_type=mime_type,
                        title=album_item.file_name,
                        can_play=True,
                        can_expand=False,
                        thumbnail=await self.async_get_thumbnail(
                            album_item, diskstation
                        ),
                    )
                )
        return ret

    async def async_resolve_media(self, item: MediaSourceItem) -> PlayMedia:
        """Resolve media to a url."""
        identifier = SynologyPhotosMediaSourceIdentifier(item.identifier)
        if identifier.album_id is None:
            raise Unresolvable("No album id")
        if identifier.file_name is None:
            raise Unresolvable("No file name")
        mime_type, _ = mimetypes.guess_type(identifier.file_name)
        if not isinstance(mime_type, str):
            raise Unresolvable("No file extension")
        suffix = ""
        if identifier.is_shared:
            suffix = SHARED_SUFFIX
        return PlayMedia(
            (
                f"/synology_dsm/{identifier.unique_id}/"
                f"{identifier.cache_key}/"
                f"{identifier.file_name}{suffix}/"
                f"{identifier.passphrase}"
            ),
            mime_type,
        )

    async def async_get_thumbnail(
        self, item: SynoPhotosItem, diskstation: SynologyDSMData
    ) -> str | None:
        """Get thumbnail."""
        if TYPE_CHECKING:
            assert diskstation.api.photos is not None

        try:
            thumbnail = await diskstation.api.photos.get_item_thumbnail_url(item)
        except SynologyDSMException:
            return None
        return str(thumbnail)


class SynologyDsmMediaView(http.HomeAssistantView):
    """Synology Media Finder View."""

    url = "/synology_dsm/{source_dir_id}/{location:.*}"
    name = "synology_dsm"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the media view."""
        self.hass = hass

    async def get(
        self, request: web.Request, source_dir_id: str, location: str
    ) -> web.Response:
        """Handle GET request with HTTP Range support for efficient video streaming."""

        if not self.hass.config_entries.async_loaded_entries(DOMAIN):
            LOGGER.error("No loaded entries for domain %s", DOMAIN)
            raise web.HTTPNotFound
        # location: {cache_key}/{filename}
        try:
            cache_key, file_name, passphrase = location.split("/")
            image_id = int(cache_key.split("_")[0])
        except (ValueError, IndexError) as exc:
            LOGGER.error("Failed to parse location %s: %s", location, exc)
            raise web.HTTPNotFound from exc

        if shared := file_name.endswith(SHARED_SUFFIX):
            file_name = file_name.removesuffix(SHARED_SUFFIX)

        mime_type, _ = mimetypes.guess_type(file_name)
        if not isinstance(mime_type, str):
            LOGGER.error("Could not determine mime type for %s", file_name)
            raise web.HTTPNotFound

        entry: SynologyDSMConfigEntry | None = (
            self.hass.config_entries.async_entry_for_domain_unique_id(
                DOMAIN, source_dir_id
            )
        )
        if TYPE_CHECKING:
            assert entry
        if not entry:
            LOGGER.error("No config entry found for %s", source_dir_id)
            raise web.HTTPNotFound

        diskstation = entry.runtime_data
        if TYPE_CHECKING:
            assert diskstation.api.photos is not None

        # Check if this is a range request for video streaming
        range_header = request.headers.get("Range")

        # Handle the request based on file type and range requirements
        item = SynoPhotosItem(image_id, "", "", "", cache_key, "xl", shared, passphrase)
        content = None
        try:
            if passphrase:
                content = await diskstation.api.photos.download_item_thumbnail(item)
                # Thumbnails are small, handle any range request in memory
                if range_header and content:
                    return self._handle_range_request_from_content(
                        content, mime_type, range_header
                    )
            elif mime_type.startswith("video/"):
                # For video files, forward range requests directly to Synology for efficient streaming
                if range_header:
                    # Optimize common inefficient range requests
                    optimized_range = self._optimize_range_request(range_header)
                    result = await self._download_item_raw(
                        diskstation, item, optimized_range
                    )
                    # Synology should return only the requested range, so return as-is with 206 status
                    if result:
                        # Handle tuple return from 206 responses with headers
                        if isinstance(result, tuple):
                            content, headers = result
                        else:
                            content = result
                            headers = None
                        return await self._handle_synology_range_response(
                            content, mime_type, optimized_range, request, headers
                        )
                else:
                    # Full video download (less common)
                    result = await self._download_item_raw(diskstation, item)
                    content = result[0] if isinstance(result, tuple) else result
            else:
                # Regular image files
                content = await diskstation.api.photos.download_item(item)
        except SynologyDSMException as exc:
            raise web.HTTPNotFound from exc

        if not content:
            raise web.HTTPNotFound

        return web.Response(body=content, content_type=mime_type)

    async def _download_item_raw(
        self,
        diskstation: SynologyDSMData,
        item: SynoPhotosItem,
        range_header: str | None = None,
    ) -> bytes | tuple[bytes, dict] | None:
        """Download item using raw binary response to avoid UTF-8 decoding issues.

        Handles HTTP Range Requests by forwarding them to Synology DSM API.
        Returns either bytes for successful regular downloads, or a tuple of
        (bytes, headers) for successful 206 Partial Content responses.
        """
        if TYPE_CHECKING:
            assert diskstation.api.photos is not None

        # Use the same API logic as Photos.download_item but with raw_response_content=True
        download_api = diskstation.api.photos.DOWNLOAD_API_KEY
        if item.is_shared:
            download_api = diskstation.api.photos.DOWNLOAD_FOTOTEAM_API_KEY

        params = {
            "unit_id": f"[{item.item_id}]",
            "cache_key": item.thumbnail_cache_key,
        }

        if item.passphrase:
            params["passphrase"] = item.passphrase

        try:
            # Prepare headers for range request forwarding
            headers = {}
            if range_header:
                headers["Range"] = range_header

            # Call DSM API directly with raw_response_content=True to get binary data
            raw_data = await diskstation.api.dsm.get(
                download_api,
                "download",
                params,
                raw_response_content=True,
                headers=headers,
            )
            if isinstance(raw_data, bytes):
                return raw_data

            # Handle StreamReader for large files
            if isinstance(raw_data, StreamReader):
                return await raw_data.read()

            LOGGER.warning("Downloaded data is unexpected type: %s", type(raw_data))
            return None
        except SynologyDSMException as exc:
            # Check if this is actually a successful 206 Partial Content response
            # The DSM library incorrectly treats 206 as an error, but it's valid for Range Requests
            if range_header:
                # The aiohttp ClientError contains the response object
                if hasattr(exc, "__cause__") and exc.__cause__:
                    cause = exc.__cause__
                    # For aiohttp ClientError, the response is the first argument
                    if hasattr(cause, "args") and cause.args:
                        response = cause.args[0]

                        if hasattr(response, "status") and response.status == 206:
                            try:
                                content = await response.read()
                                # Return tuple with content and headers since bytes can't have attributes
                                return (content, response.headers)
                            except Exception:
                                LOGGER.exception(
                                    "Could not read content from 206 response"
                                )

            LOGGER.exception("Error downloading item")
            return None

    def _optimize_range_request(self, range_header: str) -> str:
        """Optimize inefficient range requests for better streaming performance.

        Converts full-file requests (bytes=0-) to smaller initial chunks
        to enable faster video startup. Other range requests pass through unchanged.
        """
        # Parse range header: "bytes=start-end" or "bytes=start-"
        range_match = re.match(r"bytes=(\d+)-(\d*)", range_header)
        if not range_match:
            return range_header

        start = int(range_match.group(1))
        end_str = range_match.group(2)

        # If this is a request for the entire file from beginning (bytes=0-),
        # limit it to first 10MB for faster initial video loading
        if start == 0 and not end_str:
            return "bytes=0-10485759"  # 10MB - 1 byte

        # For other range requests, pass through as-is
        return range_header

    def _handle_range_request_from_content(
        self, content: bytes, mime_type: str, range_header: str
    ) -> web.Response:
        """Handle Range Request from already downloaded content."""
        # Parse range header: "bytes=start-end" or "bytes=start-"
        range_match = re.match(r"bytes=(\d+)-(\d*)", range_header)
        if not range_match:
            raise web.HTTPRequestRangeNotSatisfiable

        start = int(range_match.group(1))
        end_str = range_match.group(2)
        total_size = len(content)

        # Calculate end position
        if end_str:
            end = min(int(end_str), total_size - 1)
        else:
            end = total_size - 1

        # Validate range
        if start >= total_size or start > end:
            raise web.HTTPRequestRangeNotSatisfiable

        # Extract the requested byte range
        range_content = content[start : end + 1]

        # Return HTTP 206 Partial Content response
        headers = {
            "Content-Range": f"bytes {start}-{end}/{total_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(len(range_content)),
            "Content-Type": mime_type,
        }

        return web.Response(body=range_content, status=206, headers=headers)

    async def _handle_synology_range_response(
        self,
        content: bytes,
        mime_type: str,
        range_header: str,
        request: web.Request,
        synology_headers: dict | None = None,
    ) -> web.Response:
        """Handle range response from Synology that should already contain the requested range."""
        if synology_headers and "Content-Range" in synology_headers:
            # Use Synology's exact Content-Range header for accurate range information
            content_range = synology_headers["Content-Range"]

            headers = {
                "Content-Range": content_range,
                "Accept-Ranges": "bytes",
                "Content-Length": str(len(content)),
                "Content-Type": mime_type,
            }

            # Copy other relevant headers from Synology
            if "Last-Modified" in synology_headers:
                headers["Last-Modified"] = synology_headers["Last-Modified"]
            if "Etag" in synology_headers:
                headers["Etag"] = synology_headers["Etag"]

            return web.Response(body=content, status=206, headers=headers)

        # Fallback to parsing the range request if we don't have Synology headers
        range_match = re.match(r"bytes=(\d+)-(\d*)", range_header)
        if not range_match:
            # If we can't parse the range, return the content as-is with 206 status
            return web.Response(
                body=content,
                content_type=mime_type,
                status=206,
                headers={"Accept-Ranges": "bytes", "Content-Length": str(len(content))},
            )

        start = int(range_match.group(1))
        content_length = len(content)

        # Calculate the actual end position based on what we received
        # Since Synology returned only the requested range, end = start + content_length - 1
        end = start + content_length - 1

        # For Range responses, we typically know the total file size from Synology's headers
        # But since we're forwarding the request, we may not have this info
        # Using "*" is valid for HTTP 206 when total size is unknown
        total_size = "*"

        headers = {
            "Content-Range": f"bytes {start}-{end}/{total_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(content_length),
            "Content-Type": mime_type,
        }

        return web.Response(body=content, status=206, headers=headers)
