"""Expose Reolink IP camera VODs as media sources."""

from __future__ import annotations

import datetime as dt

from homeassistant.components.media_player import BrowseError, MediaClass, MediaType
from homeassistant.components.media_source.error import Unresolvable
from homeassistant.components.media_source.models import (
    BrowseMediaSource,
    MediaSource,
    MediaSourceItem,
    PlayMedia,
)
from homeassistant.core import HomeAssistant, callback

from .camera import ReolinkCamera
from .const import DOMAIN
from .view import ReoLinkCameraDownloadView, _async_get_camera_component


async def async_get_media_source(hass: HomeAssistant) -> ReolinkVODMediaSource:
    """Set up camera media source."""
    return ReolinkVODMediaSource(hass)


_YMD = tuple[int, int | None, int | None]
_FILEORYMD = str | _YMD
IDENTIFIER = tuple[str, _FILEORYMD | None]


class ReolinkVODMediaSource(MediaSource):
    """Provide Reolink camera VODs as media sources."""

    name: str = "Reolink"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize ReolinkVODMediaSource."""
        super().__init__(DOMAIN)
        self.hass = hass

    @callback
    def async_parse_identifier(self, item: MediaSourceItem) -> IDENTIFIER | None:
        """Parse identifier."""

        if item.domain != DOMAIN:
            raise Unresolvable("Unknown domain.")

        if not item.identifier:
            return None

        file_name: _FILEORYMD | None
        entity_id, _, file_name = item.identifier.partition("/")
        # pylint: disable=too-many-nested-blocks
        if file_name:
            part, _, identifier = file_name.partition("/")
            month: int | None = None
            day: int | None = None
            if part.isdigit():
                year: int | None = int(part)
                if identifier:
                    part, _, identifier = identifier.partition("/")
                    if part.isdigit():
                        month = int(part)
                        if identifier:
                            part, _, identifier = identifier.partition("/")
                            if part.isdigit() and not identifier:
                                day = int(part)
                            else:
                                year = None
                                month = None
                        else:
                            day = None
                    else:
                        year = None
                        month = None
            else:
                year = None

            if year is not None:
                file_name = (year, month, day)
        else:
            file_name = None

        return (entity_id, file_name)

    async def async_resolve_media(self, item: MediaSourceItem) -> PlayMedia:
        """Resolve media to a url."""

        identifier = self.async_parse_identifier(item)
        if not identifier:
            raise Unresolvable("Could not resolve identifier.")
        entity_id, file_name = identifier
        if not entity_id or not isinstance(file_name, str):
            raise Unresolvable("Could not resolve file.")

        component = _async_get_camera_component(self.hass)
        if not isinstance(component.get_entity(entity_id), ReolinkCamera):
            raise Unresolvable("Invalid camera.")

        return PlayMedia(
            ReoLinkCameraDownloadView.url.replace(":.*}", "}").format(
                entity_id=entity_id, filename=file_name
            ),
            "video/mp4",
        )

    async def async_browse_media(
        self,
        item: MediaSourceItem,
    ) -> BrowseMediaSource:
        """Return media."""

        try:
            parsed = self.async_parse_identifier(item)
        except Unresolvable as err:
            raise BrowseError(str(err)) from err

        if parsed:
            (entity_id, identifier) = parsed
            if entity_id:
                component = _async_get_camera_component(self.hass)
                if isinstance(
                    camera := component.get_entity(entity_id), ReolinkCamera
                ) and not isinstance(identifier, str):
                    return await self._generate_camera(camera, identifier)

        return await self._generate_root(item)

    async def _generate_camera(self, camera: ReolinkCamera, ymd: _YMD | None):
        children = []
        not_shown = 0

        if not ymd:
            # we want today of the camera, not necessarily today of the server
            now = await camera.async_get_camera_time()
            ymd = (now.year, now.month, None)
        else:
            now = None

        year, month, day = ymd
        status_only = day is None

        end = dt.date(year, month or 1, day or 1)
        start = end
        if not month:
            end = dt.date(year + 1, 1, 1) - dt.timedelta(days=1)
        elif not day:
            start -= dt.timedelta(days=1)

        identifier = "/".join(str(val) for val in ymd if val)
        identifier = f"/{identifier}"

        (statuses, files) = await camera.handle_async_download_search(
            start, end, status_only
        )

        if len(files) > 0:
            for file in files:
                file_name = f"{file.start_time.time()} {file.duration} "
                if file.triggers != file.triggers.NONE:
                    file_name += " " + " ".join(
                        str(trigger.name).title()
                        for trigger in file.triggers
                        if trigger != trigger.NONE
                    )

                children.append(
                    BrowseMediaSource(
                        domain=DOMAIN,
                        identifier=f"{camera.entity_id}/{file.file_name}",
                        media_class=MediaClass.VIDEO,
                        media_content_type=MediaType.VIDEO,
                        title=file_name,
                        # pylint: disable=fixme
                        # TODO : thumbnail="", figure out efficient way to grab/hold thumbs of VODs
                        can_play=True,
                        can_expand=False,
                    )
                )
        else:
            for status in statuses:
                if (
                    not month
                    or (end - start).days > 1
                    or (status.year == year and status.month == month)
                ):
                    for sday in status.days:
                        children.append(
                            BrowseMediaSource(
                                domain=DOMAIN,
                                identifier=f"{camera.entity_id}/{status.year}/{status.month}/{sday}",
                                media_class=MediaClass.DIRECTORY,
                                media_content_type=MediaType.PLAYLIST,
                                title=f"{status.year}/{status.month}/{sday}",
                                can_play=False,
                                can_expand=True,
                            )
                        )
                else:
                    not_shown += 1

        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=f"{camera.entity_id}{identifier}",
            media_class=MediaClass.CHANNEL,
            media_content_type=MediaType.PLAYLIST,
            title=camera.name,
            can_play=False,
            can_expand=True,
            children=children,
            not_shown=not_shown,
        )

    async def _generate_root(self, item: MediaSourceItem):
        if item.identifier:
            raise BrowseError("Unknown item")

        # Root. List cameras.
        component = _async_get_camera_component(self.hass)
        children = []
        not_shown = 0
        for camera in component.entities:
            if not isinstance(camera, ReolinkCamera):
                continue

            # for now ignore NVR's (via_device is set for them) until a proper solution is found
            if (dev_info := camera.device_info) and dev_info.get(
                "via_device"
            ) is not None:
                continue

            children.append(
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier=camera.entity_id,
                    media_class=MediaClass.CHANNEL,
                    media_content_type=MediaType.PLAYLIST,
                    title=camera.name,
                    thumbnail=f"/api/camera_proxy/{camera.entity_id}",
                    can_play=False,
                    can_expand=True,
                )
            )

        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=None,
            media_class=MediaClass.APP,
            media_content_type="",
            title="Reolink",
            can_play=False,
            can_expand=True,
            children=children,
            not_shown=not_shown,
        )
