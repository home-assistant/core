"""INDI Allsky Media Source Implementation."""

import logging
from typing import override

from aiohttp import ClientError
import yarl

from homeassistant.components.media_player import MediaClass, MediaType
from homeassistant.components.media_source import (
    BrowseMediaSource,
    MediaSource,
    MediaSourceError,
    MediaSourceItem,
    PlayMedia,
    Unresolvable,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .coordinator import IndiAllSkyConfigEntry

_LOGGER = logging.getLogger(__name__)

CATEGORY_LATEST = "latest"
CATEGORY_VIDEOS = "videos"
CATEGORY_IMAGES = "images"

CATEGORY_NAMES = {
    CATEGORY_LATEST: "Latest Media",
    CATEGORY_VIDEOS: "Timelapses & Generated Media",
    CATEGORY_IMAGES: "Captured Images History",
}


async def async_get_media_source(hass: HomeAssistant) -> IndiAllSkyMediaSource:
    """Set up INDI Allsky media source."""
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

        if not entry_id or not path:
            raise Unresolvable(
                translation_domain=DOMAIN,
                translation_key="incomplete_media_identifier",
            )

        entry = self._get_config_entry_or_raise(entry_id)
        url = entry.runtime_data.client.get_media_url(path)

        # Endpoints like latestimage, latestkeogram, lateststartrail, latesttimelapse
        # return a 302 redirect with Location header pointing to the actual media asset file.
        if path.startswith("latest"):
            session = async_get_clientsession(self.hass)
            try:
                async with session.get(url, allow_redirects=False) as resp:
                    if resp.status in (301, 302, 303, 307, 308):
                        location = resp.headers.get("Location")
                        if location:
                            url = str(yarl.URL(url).join(yarl.URL(location)))
            except (ClientError, TimeoutError) as err:
                _LOGGER.debug(
                    "Could not resolve redirect location for %s: %s", url, err
                )

        clean_url = url.split("?")[0].lower()
        if path == "latesttimelapse" or clean_url.endswith(
            (".mp4", ".mkv", ".webm", ".mov", ".avi")
        ):
            mime_type = "video/mp4"
        else:
            mime_type = "image/jpeg"
        return PlayMedia(url, mime_type)

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
        entry = self._get_config_entry_or_raise(entry_id)

        if len(parts) == 1:
            return self._build_instance_categories(entry)

        category = parts[1]
        if category == CATEGORY_LATEST:
            return self._build_latest_media(entry)

        if category == CATEGORY_VIDEOS:
            return await self._browse_videos(entry, parts[2:])

        if category == CATEGORY_IMAGES:
            return await self._browse_images(entry, parts[2:])

        raise MediaSourceError(
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
        """Get config entry or raise MediaSourceError."""
        entry = self.hass.config_entries.async_get_entry(entry_id)
        if not entry or entry.state is not ConfigEntryState.LOADED:
            raise MediaSourceError(
                translation_domain=DOMAIN,
                translation_key="config_entry_not_found",
            )
        return entry

    def _build_root_instances(self) -> BrowseMediaSource:
        """Build root media sources listing all configured INDI Allsky instances."""
        entries = self.hass.config_entries.async_entries(DOMAIN)
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
        client = entry.runtime_data.client
        children: list[BrowseMediaSource] = [
            BrowseMediaSource(
                domain=DOMAIN,
                identifier=f"{entry.entry_id}#media#latestimage",
                media_class=MediaClass.IMAGE,
                media_content_type=MediaType.IMAGE,
                title="Latest Snapshot",
                can_play=True,
                can_expand=False,
                thumbnail=client.get_media_url("latestimage"),
            ),
            BrowseMediaSource(
                domain=DOMAIN,
                identifier=f"{entry.entry_id}#media#latestkeogram",
                media_class=MediaClass.IMAGE,
                media_content_type=MediaType.IMAGE,
                title="Latest Keogram",
                can_play=True,
                can_expand=False,
                thumbnail=client.get_media_url("latestkeogram"),
            ),
            BrowseMediaSource(
                domain=DOMAIN,
                identifier=f"{entry.entry_id}#media#lateststartrail",
                media_class=MediaClass.IMAGE,
                media_content_type=MediaType.IMAGE,
                title="Latest Star Trail",
                can_play=True,
                can_expand=False,
                thumbnail=client.get_media_url("lateststartrail"),
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

        # Level 1: Years
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

        # Level 2: Months
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

        # Level 3: Videos in Year + Month
        month = int(path_parts[1])
        videos = await client.get_videos(year, month)
        children = []
        seen_media_urls: set[str] = set()

        for vid in videos:
            if not vid.success or not vid.url:
                continue

            tod_str = "Night" if vid.night else "Day"
            date_str = vid.day_date_long or vid.day_date
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

            # If keogram or star trail exists for that session, include them as child media
            if vid.keogram_url and vid.keogram_url not in seen_media_urls:
                seen_media_urls.add(vid.keogram_url)
                children.append(
                    BrowseMediaSource(
                        domain=DOMAIN,
                        identifier=f"{entry.entry_id}#media#{vid.keogram_url}",
                        media_class=MediaClass.IMAGE,
                        media_content_type=MediaType.IMAGE,
                        title=f"{tod_str} Keogram - {date_str}",
                        can_play=True,
                        can_expand=False,
                        thumbnail=client.get_media_url(vid.keogram_thumbnail_url)
                        if vid.keogram_thumbnail_url
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
                        thumbnail=client.get_media_url(st_thumb) if st_thumb else None,
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

        # Level 1: Years
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

        # Level 2: Months
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

        # Level 3: Days
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

        # Level 4: Hours
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

        # Level 5: Images in that hour
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
                thumbnail=client.get_media_url(img.url),
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
