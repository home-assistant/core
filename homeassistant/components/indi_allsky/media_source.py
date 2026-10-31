"""INDI Allsky Media Source Implementation."""

import base64
import logging
import mimetypes
from pathlib import PurePath
from typing import override
from urllib.parse import unquote

from aiohttp import ClientError, ClientTimeout, web
from aioindiallsky import IndiAllSkyError
import yarl

from homeassistant.components.http import HomeAssistantView
from homeassistant.components.media_player import BrowseError, MediaClass, MediaType
from homeassistant.components.media_source import (
    BrowseMediaSource,
    MediaSource,
    MediaSourceItem,
    PlayMedia,
    Unresolvable,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .coordinator import IndiAllSkyConfigEntry

_LOGGER = logging.getLogger(__name__)

REDIRECT_TIMEOUT = ClientTimeout(total=10)
STREAM_TIMEOUT = ClientTimeout(connect=10, sock_read=10, total=None)
MEDIA_STREAM_CHUNK_SIZE = 64 * 1024

CATEGORY_LATEST = "latest"
CATEGORY_VIDEOS = "videos"
CATEGORY_IMAGES = "images"

CATEGORY_NAMES = {
    CATEGORY_LATEST: "Latest Media",
    CATEGORY_VIDEOS: "Timelapses & Generated Media",
    CATEGORY_IMAGES: "Captured Images History",
}

MEDIA_PROXY_URL = "/api/indi_allsky/media/{entry_id}/{path}"

VALID_PROXY_MEDIA_EXACT_PATHS = {
    "latestimage",
    "latestkeogram",
    "lateststartrail",
    "latesttimelapse",
}

VALID_PROXY_MEDIA_PREFIXES = (
    "images/",
    "public/",
)


def _canonicalize_media_path(media_path: str) -> str | None:
    """Decode a media path to a stable canonical form, or None if cyclic/invalid."""
    current = media_path
    for _ in range(10):
        unquoted = unquote(current)
        if unquoted == current:
            return current
        current = unquoted
    return None


def _is_valid_media_path(media_path: str) -> bool:
    """Validate that the media path targets an allowed INDI Allsky media route."""
    if media_path in VALID_PROXY_MEDIA_EXACT_PATHS:
        return True
    return media_path.startswith(VALID_PROXY_MEDIA_PREFIXES)


def _is_same_origin(source: yarl.URL, target: yarl.URL) -> bool:
    """Check that two URLs share the same scheme, host, and port."""
    return (
        target.scheme == source.scheme
        and target.host == source.host
        and target.port == source.port
    )


def _encode_media_path(path: str) -> str:
    """Encode an INDI Allsky media path for use in a Home Assistant proxy URL."""
    return base64.urlsafe_b64encode(path.encode("utf-8")).decode("ascii")


def _build_media_proxy_path(entry_id: str, path: str) -> str:
    """Build a Home Assistant proxy path for INDI Allsky media."""
    return MEDIA_PROXY_URL.format(
        entry_id=entry_id,
        path=_encode_media_path(path),
    )


class IndiAllSkyMediaProxyView(HomeAssistantView):
    """Proxy INDI Allsky media assets through Home Assistant."""

    requires_auth = True
    url = MEDIA_PROXY_URL
    name = "api:indi_allsky:media"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the proxy view."""
        self.hass = hass

    async def head(
        self,
        request: web.Request,
        entry_id: str,
        path: str,
    ) -> web.StreamResponse:
        """Handle HEAD requests for media assets."""
        return await self._handle_request(request, entry_id, path)

    async def get(
        self,
        request: web.Request,
        entry_id: str,
        path: str,
    ) -> web.StreamResponse:
        """Stream media assets from the INDI Allsky device."""
        return await self._handle_request(request, entry_id, path)

    async def _handle_request(
        self,
        request: web.Request,
        entry_id: str,
        path: str,
    ) -> web.StreamResponse:
        """Handle media asset requests from the INDI Allsky device."""
        entry = self.hass.config_entries.async_get_entry(entry_id)
        if (
            not entry
            or entry.domain != DOMAIN
            or entry.state is not ConfigEntryState.LOADED
        ):
            return web.Response(status=404)

        try:
            media_path = base64.b64decode(
                path.encode("ascii"), altchars=b"-_", validate=True
            ).decode("utf-8")
        except ValueError, UnicodeError:
            return web.Response(status=400)

        canonical_media_path = _canonicalize_media_path(media_path)
        if canonical_media_path is None:
            return web.Response(status=400)

        media_path_obj = PurePath(canonical_media_path)
        if (
            media_path_obj.is_absolute()
            or ".." in media_path_obj.parts
            or any(char in canonical_media_path for char in "\t\r\n")
            or not _is_valid_media_path(media_path)
            or not _is_valid_media_path(canonical_media_path)
        ):
            return web.Response(status=400)

        url = entry.runtime_data.client.get_media_url(media_path)
        verify_ssl: bool = entry.data.get(CONF_VERIFY_SSL, True)
        session = async_get_clientsession(self.hass, verify_ssl=verify_ssl)

        headers: dict[str, str] = {}
        if range_header := request.headers.get("Range"):
            headers["Range"] = range_header

        url_obj = yarl.URL(url)
        response: web.StreamResponse | None = None
        try:
            current_url = url
            session_method = session.head if request.method == "HEAD" else session.get
            for _ in range(5):
                async with session_method(
                    current_url,
                    headers=headers,
                    timeout=STREAM_TIMEOUT,
                    allow_redirects=False,
                    auto_decompress=False,
                ) as upstream:
                    if upstream.status in (301, 302, 303, 307, 308):
                        location = upstream.headers.get("Location")
                        if not location:
                            return web.Response(status=502)
                        try:
                            target_url = yarl.URL(current_url).join(yarl.URL(location))
                        except ValueError:
                            return web.Response(status=502)
                        if not _is_same_origin(url_obj, target_url):
                            return web.Response(status=502)
                        current_url = str(target_url)
                        continue

                    resp_headers: dict[str, str] = {}
                    for header in (
                        "Accept-Ranges",
                        "Content-Encoding",
                        "Content-Length",
                        "Content-Range",
                        "Content-Type",
                    ):
                        if val := upstream.headers.get(header):
                            resp_headers[header] = val

                    response = web.StreamResponse(
                        status=upstream.status,
                        headers=resp_headers,
                    )

                    if "Content-Type" not in resp_headers:
                        clean_url = str(upstream.url).split("?", maxsplit=1)[0].lower()
                        if mime := mimetypes.guess_type(clean_url)[0]:
                            response.content_type = mime
                        elif media_path == "latesttimelapse":
                            response.content_type = "video/mp4"
                        else:
                            response.content_type = "image/jpeg"

                    response.headers["Content-Security-Policy"] = "sandbox"
                    await response.prepare(request)

                    if request.method != "HEAD":
                        async for chunk in upstream.content.iter_chunked(
                            MEDIA_STREAM_CHUNK_SIZE
                        ):
                            await response.write(chunk)

                    await response.write_eof()
                    return response

            return web.Response(status=502)
        except ClientError, TimeoutError:
            if response is not None and response.prepared:
                raise
            return web.Response(status=502)


async def async_get_media_source(hass: HomeAssistant) -> IndiAllSkyMediaSource:
    """Set up INDI Allsky media source."""
    hass.http.register_view(IndiAllSkyMediaProxyView(hass))
    return IndiAllSkyMediaSource(hass)


class IndiAllSkyMediaSource(MediaSource):
    """Provide INDI Allsky media items as a media source."""

    name: str = "INDI Allsky"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize IndiAllSkyMediaSource."""
        super().__init__(DOMAIN)
        self.hass = hass

    @override
    async def async_resolve_media(self, item: MediaSourceItem) -> PlayMedia:
        """Resolve media item to a URL and mime type."""
        entry_id, path = self._parse_identifier(item.identifier)

        if not entry_id or not path or not _is_valid_media_path(path):
            raise Unresolvable(
                translation_domain=DOMAIN,
                translation_key="incomplete_media_identifier",
            )

        entry = self._get_config_entry_or_raise(entry_id)
        url = entry.runtime_data.client.get_media_url(path)
        url_obj = yarl.URL(url)

        # Endpoints like latestimage, latestkeogram, lateststartrail, latesttimelapse
        # return a 302 redirect with Location header pointing to the actual media asset file.
        content_type: str | None = None
        if path.startswith("latest"):
            verify_ssl: bool = entry.data.get(CONF_VERIFY_SSL, True)
            session = async_get_clientsession(self.hass, verify_ssl=verify_ssl)
            try:
                async with session.get(
                    url, allow_redirects=False, timeout=REDIRECT_TIMEOUT
                ) as resp:
                    if resp.status in (301, 302, 303, 307, 308):
                        location = resp.headers.get("Location")
                        if location:
                            try:
                                target_url = url_obj.join(yarl.URL(location))
                                if _is_same_origin(url_obj, target_url):
                                    url = str(target_url)
                            except ValueError:
                                pass
                    elif resp.status == 200:
                        content_type = resp.headers.get("Content-Type")
            except (ClientError, TimeoutError) as err:
                _LOGGER.debug(
                    "Could not resolve redirect location for %s: %s", url, err
                )

        clean_url = url.split("?", maxsplit=1)[0].lower()
        if mime := mimetypes.guess_type(clean_url)[0]:
            mime_type = mime
        elif content_type:
            mime_type = content_type.split(";")[0].strip()
        elif path == "latesttimelapse":
            mime_type = "video/mp4"
        else:
            mime_type = "image/jpeg"
        proxy_path = _build_media_proxy_path(entry.entry_id, path)
        return PlayMedia(proxy_path, mime_type)

    @override
    async def async_browse_media(
        self,
        item: MediaSourceItem,
    ) -> BrowseMediaSource:
        """Return media items for browsing."""
        if not item.identifier:
            return self._build_root_instances()

        parts = item.identifier.split("#")
        entry_id = parts[0]
        try:
            entry = self._get_config_entry_or_raise(entry_id)
        except Unresolvable as err:
            raise BrowseError(
                translation_domain=err.translation_domain,
                translation_key=err.translation_key,
                translation_placeholders=err.translation_placeholders,
            ) from err

        if len(parts) == 1:
            return self._build_instance_categories(entry)

        category = parts[1]
        extra_parts = parts[2:]
        try:
            if category == CATEGORY_LATEST and not extra_parts:
                return self._build_latest_media(entry)

            if category == CATEGORY_VIDEOS and len(extra_parts) <= 2:
                return await self._browse_videos(entry, extra_parts)

            if category == CATEGORY_IMAGES and len(extra_parts) <= 4:
                return await self._browse_images(entry, extra_parts)
        except ValueError as err:
            raise BrowseError(
                translation_domain=DOMAIN,
                translation_key="incomplete_media_identifier",
            ) from err
        except IndiAllSkyError as err:
            raise BrowseError(
                translation_domain=DOMAIN,
                translation_key="update_failed",
            ) from err

        raise BrowseError(
            translation_domain=DOMAIN,
            translation_key="incomplete_media_identifier",
        )

    @callback
    def _parse_identifier(self, identifier: str) -> tuple[str | None, str | None]:
        """Parse entry_id and target path from identifier."""
        if "#" in identifier:
            parts = identifier.split("#", 2)
            if len(parts) == 3 and parts[1] == "media":
                return parts[0], parts[2]
            if len(parts) == 2 and parts[1].startswith("public/"):
                return parts[0], parts[1]
        return identifier, None

    def _get_config_entry_or_raise(self, entry_id: str) -> IndiAllSkyConfigEntry:
        """Get config entry or raise Unresolvable."""
        entry = self.hass.config_entries.async_get_entry(entry_id)
        if (
            not entry
            or entry.domain != DOMAIN
            or entry.state is not ConfigEntryState.LOADED
        ):
            raise Unresolvable(
                translation_domain=DOMAIN,
                translation_key="config_entry_not_found",
            )
        return entry

    def _build_root_instances(self) -> BrowseMediaSource:
        """Build root media sources listing all configured INDI Allsky instances."""
        entries = self.hass.config_entries.async_loaded_entries(DOMAIN)
        return BrowseMediaSource(
            domain=DOMAIN,
            identifier="",
            media_class=MediaClass.DIRECTORY,
            media_content_type="",
            title=self.name,
            can_play=False,
            can_expand=True,
            children=[
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier=entry.entry_id,
                    media_class=MediaClass.DIRECTORY,
                    media_content_type="",
                    title=entry.title,
                    can_play=False,
                    can_expand=True,
                    children_media_class=MediaClass.DIRECTORY,
                )
                for entry in entries
            ],
            children_media_class=MediaClass.DIRECTORY,
        )

    def _build_instance_categories(
        self, entry: IndiAllSkyConfigEntry
    ) -> BrowseMediaSource:
        """Build top-level categories for an INDI Allsky instance."""
        children = [
            BrowseMediaSource(
                domain=DOMAIN,
                identifier=f"{entry.entry_id}#{CATEGORY_LATEST}",
                media_class=MediaClass.DIRECTORY,
                media_content_type="",
                title=CATEGORY_NAMES[CATEGORY_LATEST],
                can_play=False,
                can_expand=True,
            ),
            BrowseMediaSource(
                domain=DOMAIN,
                identifier=f"{entry.entry_id}#{CATEGORY_VIDEOS}",
                media_class=MediaClass.DIRECTORY,
                media_content_type="",
                title=CATEGORY_NAMES[CATEGORY_VIDEOS],
                can_play=False,
                can_expand=True,
                children_media_class=MediaClass.DIRECTORY,
            ),
            BrowseMediaSource(
                domain=DOMAIN,
                identifier=f"{entry.entry_id}#{CATEGORY_IMAGES}",
                media_class=MediaClass.DIRECTORY,
                media_content_type="",
                title=CATEGORY_NAMES[CATEGORY_IMAGES],
                can_play=False,
                can_expand=True,
                children_media_class=MediaClass.DIRECTORY,
            ),
        ]

        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=entry.entry_id,
            media_class=MediaClass.DIRECTORY,
            media_content_type="",
            title=entry.title,
            can_play=False,
            can_expand=True,
            children=children,
            children_media_class=MediaClass.DIRECTORY,
        )

    def _build_latest_media(self, entry: IndiAllSkyConfigEntry) -> BrowseMediaSource:
        """Build latest available media items."""
        children: list[BrowseMediaSource] = [
            BrowseMediaSource(
                domain=DOMAIN,
                identifier=f"{entry.entry_id}#media#latestimage",
                media_class=MediaClass.IMAGE,
                media_content_type=MediaType.IMAGE,
                title="Latest Snapshot",
                can_play=True,
                can_expand=False,
                thumbnail=_build_media_proxy_path(entry.entry_id, "latestimage"),
            ),
            BrowseMediaSource(
                domain=DOMAIN,
                identifier=f"{entry.entry_id}#media#latestkeogram",
                media_class=MediaClass.IMAGE,
                media_content_type=MediaType.IMAGE,
                title="Latest Keogram",
                can_play=True,
                can_expand=False,
                thumbnail=_build_media_proxy_path(entry.entry_id, "latestkeogram"),
            ),
            BrowseMediaSource(
                domain=DOMAIN,
                identifier=f"{entry.entry_id}#media#lateststartrail",
                media_class=MediaClass.IMAGE,
                media_content_type=MediaType.IMAGE,
                title="Latest Star Trail",
                can_play=True,
                can_expand=False,
                thumbnail=_build_media_proxy_path(entry.entry_id, "lateststartrail"),
            ),
            BrowseMediaSource(
                domain=DOMAIN,
                identifier=f"{entry.entry_id}#media#latesttimelapse",
                media_class=MediaClass.VIDEO,
                media_content_type=MediaType.VIDEO,
                title="Latest Timelapse",
                can_play=True,
                can_expand=False,
            ),
        ]

        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=f"{entry.entry_id}#{CATEGORY_LATEST}",
            media_class=MediaClass.DIRECTORY,
            media_content_type="",
            title=CATEGORY_NAMES[CATEGORY_LATEST],
            can_play=False,
            can_expand=True,
            children=children,
        )

    async def _browse_videos(
        self, entry: IndiAllSkyConfigEntry, path_parts: list[str]
    ) -> BrowseMediaSource:
        """Browse video catalog (Years -> Months -> Videos)."""
        client = entry.runtime_data.client

        if not path_parts:
            years = await client.get_video_years()
            children = [
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier=f"{entry.entry_id}#{CATEGORY_VIDEOS}#{yr}",
                    media_class=MediaClass.DIRECTORY,
                    media_content_type="",
                    title=str(yr),
                    can_play=False,
                    can_expand=True,
                    children_media_class=MediaClass.DIRECTORY,
                )
                for yr in years
            ]
            return BrowseMediaSource(
                domain=DOMAIN,
                identifier=f"{entry.entry_id}#{CATEGORY_VIDEOS}",
                media_class=MediaClass.DIRECTORY,
                media_content_type="",
                title=CATEGORY_NAMES[CATEGORY_VIDEOS],
                can_play=False,
                can_expand=True,
                children=children,
                children_media_class=MediaClass.DIRECTORY,
            )

        year = int(path_parts[0])

        if len(path_parts) == 1:
            months = await client.get_video_months(year)
            children = [
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier=f"{entry.entry_id}#{CATEGORY_VIDEOS}#{year}#{m.month}",
                    media_class=MediaClass.DIRECTORY,
                    media_content_type="",
                    title=m.name,
                    can_play=False,
                    can_expand=True,
                )
                for m in months
            ]
            return BrowseMediaSource(
                domain=DOMAIN,
                identifier=f"{entry.entry_id}#{CATEGORY_VIDEOS}#{year}",
                media_class=MediaClass.DIRECTORY,
                media_content_type="",
                title=str(year),
                can_play=False,
                can_expand=True,
                children=children,
                children_media_class=MediaClass.DIRECTORY,
            )

        month = int(path_parts[1])
        videos = await client.get_videos(year, month)
        children = []
        seen_media_urls: set[str] = set()

        for vid in videos:
            tod_str = "Night" if vid.night else "Day"
            date_str = vid.day_date_long or vid.day_date

            if vid.success and vid.url:
                children.append(
                    BrowseMediaSource(
                        domain=DOMAIN,
                        identifier=f"{entry.entry_id}#media#{vid.url}",
                        media_class=MediaClass.VIDEO,
                        media_content_type=MediaType.VIDEO,
                        title=f"{tod_str} Timelapse - {date_str}",
                        can_play=True,
                        can_expand=False,
                    )
                )

            if vid.keogram_url and vid.keogram_url not in seen_media_urls:
                seen_media_urls.add(vid.keogram_url)
                keo_thumb = vid.keogram_thumbnail_url or vid.keogram_url
                children.append(
                    BrowseMediaSource(
                        domain=DOMAIN,
                        identifier=f"{entry.entry_id}#media#{vid.keogram_url}",
                        media_class=MediaClass.IMAGE,
                        media_content_type=MediaType.IMAGE,
                        title=f"{tod_str} Keogram - {date_str}",
                        can_play=True,
                        can_expand=False,
                        thumbnail=_build_media_proxy_path(entry.entry_id, keo_thumb)
                        if keo_thumb
                        else None,
                    )
                )

            if vid.startrail_url and vid.startrail_url not in seen_media_urls:
                seen_media_urls.add(vid.startrail_url)
                st_thumb = vid.startrail_thumbnail_url or vid.startrail_url
                children.append(
                    BrowseMediaSource(
                        domain=DOMAIN,
                        identifier=f"{entry.entry_id}#media#{vid.startrail_url}",
                        media_class=MediaClass.IMAGE,
                        media_content_type=MediaType.IMAGE,
                        title=f"{tod_str} Star Trail - {date_str}",
                        can_play=True,
                        can_expand=False,
                        thumbnail=_build_media_proxy_path(entry.entry_id, st_thumb)
                        if st_thumb
                        else None,
                    )
                )

        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=f"{entry.entry_id}#{CATEGORY_VIDEOS}#{year}#{month}",
            media_class=MediaClass.DIRECTORY,
            media_content_type="",
            title=f"{year} - {month:02d}",
            can_play=False,
            can_expand=True,
            children=children,
        )

    async def _browse_images(
        self, entry: IndiAllSkyConfigEntry, path_parts: list[str]
    ) -> BrowseMediaSource:
        """Browse image history (Years -> Months -> Days -> Hours -> Images)."""
        client = entry.runtime_data.client

        if not path_parts:
            years = await client.get_image_years()
            children = [
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier=f"{entry.entry_id}#{CATEGORY_IMAGES}#{yr}",
                    media_class=MediaClass.DIRECTORY,
                    media_content_type="",
                    title=str(yr),
                    can_play=False,
                    can_expand=True,
                    children_media_class=MediaClass.DIRECTORY,
                )
                for yr in years
            ]
            return BrowseMediaSource(
                domain=DOMAIN,
                identifier=f"{entry.entry_id}#{CATEGORY_IMAGES}",
                media_class=MediaClass.DIRECTORY,
                media_content_type="",
                title=CATEGORY_NAMES[CATEGORY_IMAGES],
                can_play=False,
                can_expand=True,
                children=children,
                children_media_class=MediaClass.DIRECTORY,
            )

        year = int(path_parts[0])

        if len(path_parts) == 1:
            months = await client.get_image_months(year)
            children = [
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier=f"{entry.entry_id}#{CATEGORY_IMAGES}#{year}#{m.month}",
                    media_class=MediaClass.DIRECTORY,
                    media_content_type="",
                    title=m.name,
                    can_play=False,
                    can_expand=True,
                    children_media_class=MediaClass.DIRECTORY,
                )
                for m in months
            ]
            return BrowseMediaSource(
                domain=DOMAIN,
                identifier=f"{entry.entry_id}#{CATEGORY_IMAGES}#{year}",
                media_class=MediaClass.DIRECTORY,
                media_content_type="",
                title=str(year),
                can_play=False,
                can_expand=True,
                children=children,
                children_media_class=MediaClass.DIRECTORY,
            )

        month = int(path_parts[1])
        if len(path_parts) == 2:
            days = await client.get_image_days(year, month)
            children = [
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier=f"{entry.entry_id}#{CATEGORY_IMAGES}#{year}#{month}#{day}",
                    media_class=MediaClass.DIRECTORY,
                    media_content_type="",
                    title=f"Day {day:02d}",
                    can_play=False,
                    can_expand=True,
                    children_media_class=MediaClass.DIRECTORY,
                )
                for day in days
            ]
            return BrowseMediaSource(
                domain=DOMAIN,
                identifier=f"{entry.entry_id}#{CATEGORY_IMAGES}#{year}#{month}",
                media_class=MediaClass.DIRECTORY,
                media_content_type="",
                title=f"{year} - {month:02d}",
                can_play=False,
                can_expand=True,
                children=children,
                children_media_class=MediaClass.DIRECTORY,
            )

        day = int(path_parts[2])
        if len(path_parts) == 3:
            hours = await client.get_image_hours(year, month, day)
            children = [
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier=f"{entry.entry_id}#{CATEGORY_IMAGES}#{year}#{month}#{day}#{hr}",
                    media_class=MediaClass.DIRECTORY,
                    media_content_type="",
                    title=f"{hr:02d}:00 - {hr:02d}:59",
                    can_play=False,
                    can_expand=True,
                    children_media_class=MediaClass.IMAGE,
                )
                for hr in hours
            ]
            return BrowseMediaSource(
                domain=DOMAIN,
                identifier=f"{entry.entry_id}#{CATEGORY_IMAGES}#{year}#{month}#{day}",
                media_class=MediaClass.DIRECTORY,
                media_content_type="",
                title=f"{year}-{month:02d}-{day:02d}",
                can_play=False,
                can_expand=True,
                children=children,
                children_media_class=MediaClass.DIRECTORY,
            )

        hour = int(path_parts[3])
        images = await client.get_images(year, month, day, hour)
        children = [
            BrowseMediaSource(
                domain=DOMAIN,
                identifier=f"{entry.entry_id}#media#{img.url}",
                media_class=MediaClass.IMAGE,
                media_content_type=MediaType.IMAGE,
                title=f"{img.time_str} ({img.width}x{img.height})",
                can_play=True,
                can_expand=False,
            )
            for img in images
            if img.url
        ]
        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=f"{entry.entry_id}#{CATEGORY_IMAGES}#{year}#{month}#{day}#{hour}",
            media_class=MediaClass.DIRECTORY,
            media_content_type="",
            title=f"{year}-{month:02d}-{day:02d} {hour:02d}:00",
            can_play=False,
            can_expand=True,
            children=children,
            children_media_class=MediaClass.IMAGE,
        )
