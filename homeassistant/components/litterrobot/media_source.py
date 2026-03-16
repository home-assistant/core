"""Litter-Robot media source for browsing local recordings and cloud thumbnails."""

from __future__ import annotations

import logging
from pathlib import Path

from pylitterbot import LitterRobot5

from homeassistant.components.media_player import MediaClass, MediaType
from homeassistant.components.media_source import (
    BrowseMediaSource,
    MediaSource,
    MediaSourceItem,
    PlayMedia,
    Unresolvable,
)
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import LitterRobotDataUpdateCoordinator
from .http import RECORDING_ENDPOINT

_LOGGER = logging.getLogger(__name__)

MAX_LOCAL_RECORDINGS = 50


async def async_get_media_source(hass: HomeAssistant) -> LitterRobotMediaSource:
    """Set up Litter-Robot media source."""
    return LitterRobotMediaSource(hass)


class LitterRobotMediaSource(MediaSource):
    """Provide Litter-Robot local recordings and cloud thumbnails as a media source."""

    name = "Litter-Robot"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the media source."""
        super().__init__(DOMAIN)
        self.hass = hass

    def _get_camera_robots(
        self,
    ) -> list[tuple[LitterRobotDataUpdateCoordinator, LitterRobot5]]:
        """Return coordinators and LR5 Pro robots with cameras."""
        return [
            (entry.runtime_data, robot)
            for entry in self.hass.config_entries.async_loaded_entries(DOMAIN)
            for robot in entry.runtime_data.account.robots
            if isinstance(robot, LitterRobot5) and robot.has_camera
        ]

    def _get_recording_dir(self, serial: str) -> Path:
        """Return the recording directory for a robot."""
        return Path(self.hass.config.path("media")) / "litterrobot" / serial

    async def async_resolve_media(self, item: MediaSourceItem) -> PlayMedia:
        """Resolve a media item to a playable URL."""
        if not item.identifier:
            raise Unresolvable("No identifier provided")

        parts = item.identifier.split("|", 2)

        # Local recording: local|<serial>|<filename>
        if len(parts) == 3 and parts[0] == "local":
            _, serial, filename = parts
            return self._resolve_local_recording(serial, filename)

        raise Unresolvable(f"Invalid identifier: {item.identifier}")

    def _resolve_local_recording(self, serial: str, filename: str) -> PlayMedia:
        """Resolve a local MP4 recording to a playable URL."""
        # Validate filename to prevent path traversal
        if "/" in filename or "\\" in filename or ".." in filename:
            raise Unresolvable(f"Invalid filename: {filename}")

        recording_path = self._get_recording_dir(serial) / filename
        if not recording_path.exists():
            raise Unresolvable(f"Recording not found: {filename}")

        url = RECORDING_ENDPOINT.format(serial=serial, filename=filename)
        return PlayMedia(url=url, mime_type="video/mp4")

    async def async_browse_media(self, item: MediaSourceItem) -> BrowseMediaSource:
        """Browse media — list robots at root, recordings and clips per robot."""
        if not item.identifier:
            return self._browse_root()

        serial = item.identifier
        for _coordinator, robot in self._get_camera_robots():
            if robot.serial == serial:
                return await self._browse_robot(robot)

        raise Unresolvable(f"Robot {serial} not found")

    def _browse_root(self) -> BrowseMediaSource:
        """List all robots with cameras."""
        robots = self._get_camera_robots()

        base = BrowseMediaSource(
            domain=DOMAIN,
            identifier=None,
            media_class=MediaClass.DIRECTORY,
            media_content_type=MediaType.VIDEO,
            title="Litter-Robot",
            can_play=False,
            can_expand=True,
            children_media_class=MediaClass.DIRECTORY,
        )

        base.children = [
            BrowseMediaSource(
                domain=DOMAIN,
                identifier=robot.serial,
                media_class=MediaClass.DIRECTORY,
                media_content_type=MediaType.VIDEO,
                title=robot.name,
                can_play=False,
                can_expand=True,
                children_media_class=MediaClass.VIDEO,
            )
            for _coordinator, robot in robots
        ]

        return base

    async def _browse_robot(self, robot: LitterRobot5) -> BrowseMediaSource:
        """List local recordings and cloud thumbnails for a specific robot."""
        base = BrowseMediaSource(
            domain=DOMAIN,
            identifier=robot.serial,
            media_class=MediaClass.DIRECTORY,
            media_content_type=MediaType.VIDEO,
            title=robot.name,
            can_play=False,
            can_expand=True,
            children_media_class=MediaClass.VIDEO,
        )

        children: list[BrowseMediaSource] = []

        # Local recordings (newest first)
        local_recordings = await self.hass.async_add_executor_job(
            self._list_local_recordings, robot.serial
        )
        children.extend(local_recordings)

        base.children = children
        return base

    def _list_local_recordings(self, serial: str) -> list[BrowseMediaSource]:
        """List local MP4 recordings for a robot (runs in executor)."""
        recording_dir = self._get_recording_dir(serial)
        if not recording_dir.exists():
            return []

        mp4_files = sorted(
            recording_dir.glob("*.mp4"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )[:MAX_LOCAL_RECORDINGS]

        return [
            BrowseMediaSource(
                domain=DOMAIN,
                identifier=f"local|{serial}|{mp4.name}",
                media_class=MediaClass.VIDEO,
                media_content_type="video/mp4",
                title=_parse_recording_title(mp4.stem),
                can_play=True,
                can_expand=False,
            )
            for mp4 in mp4_files
        ]


def _parse_recording_title(stem: str) -> str:
    """Convert a recording filename stem to a human-readable title.

    Filename formats produced by recording.py:
      YYYYMMDD_HHMMSS_PET_VISIT_{PetName}  — pet visit with assigned name
      YYYYMMDD_HHMMSS_{EVENT_TYPE}          — other events (VISIT, CYCLE, etc.)
      YYYYMMDD_HHMMSS_{COMPOUND}_{PetName} — older VISIT_{Name} format
    """
    parts = stem.split("_", 2)
    if len(parts) < 2:
        return stem

    date_str = parts[0]
    time_str = parts[1]
    rest = parts[2] if len(parts) > 2 else ""

    date_fmt = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
    time_fmt = f"{time_str[:2]}:{time_str[2:4]}"

    if not rest:
        return f"Recording - {date_fmt} {time_fmt}"

    # Compound events that never carry a pet name after them
    COMPOUND_EVENTS = {"CYCLE_COMPLETED", "CYCLE_INTERRUPTED", "CAT_DETECT"}
    # Event types where a missing pet name means the visit was unassigned
    VISIT_EVENTS = {"VISIT", "PET_VISIT"}

    pet: str | None = None
    event = rest

    if rest.startswith("PET_VISIT_"):
        # e.g. PET_VISIT_Willow
        event = "PET_VISIT"
        pet = rest[len("PET_VISIT_") :]
    elif rest in COMPOUND_EVENTS:
        event = rest
    elif "_" in rest:
        # Could be VISIT_PetName (mixed-case pet) or a compound event type
        event_part, suffix = rest.split("_", 1)
        # Pet names start with uppercase and contain lowercase letters
        # (e.g. "Willow", "Loki"); event suffixes like "COMPLETED" are all-caps
        if suffix and suffix[0].isupper() and any(c.islower() for c in suffix):
            event = event_part
            pet = suffix
        # else: treat the whole thing as a compound event name

    # Visit-type recordings with no pet name = cat wasn't identified
    if pet is None and event in VISIT_EVENTS:
        pet = "Unassigned"

    pretty_event = event.replace("_", " ").title()
    if pet:
        return f"{pretty_event} ({pet}) - {date_fmt} {time_fmt}"
    return f"{pretty_event} - {date_fmt} {time_fmt}"
