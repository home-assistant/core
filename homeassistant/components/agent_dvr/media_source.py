"""Media Source platform for Agent DVR: browse & play recordings.

Agent DVR exposes no REST endpoint for this — browsing (getevents) and
downloading a clip both go through the reverse-engineered WebRTC data
channel in webrtc.py. See that module's docstring for the full
background.

Resolving a clip downloads it (on demand, cached) into
config/www/agent_dvr/<entry_id>/ and serves it back as a plain /local/...
URL, since there is no way to stream directly from Agent DVR's WebRTC
channel into a <video> tag.

Identifiers are `<entry_id>|<camera_key>|<filename>`, trimmed from the
right at each browse level, so browsing works with more than one
configured Agent DVR server.
"""

import logging
import mimetypes
import os

from homeassistant.components.media_player import MediaClass, MediaType
from homeassistant.components.media_source import (
    BrowseMediaSource,
    MediaSource,
    MediaSourceItem,
    PlayMedia,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import AgentDVRConfigEntry
from .const import DEVICE_TYPE_CAMERA, DOMAIN
from .webrtc import AgentDVRWebRTCError

_LOGGER = logging.getLogger(__name__)

RECORDINGS_LIMIT = 30


async def async_get_media_source(hass: HomeAssistant) -> AgentDVRMediaSource:
    """Set up the Agent DVR media source."""
    return AgentDVRMediaSource(hass)


def _get_entry(hass: HomeAssistant, entry_id: str) -> AgentDVRConfigEntry:
    entry = hass.config_entries.async_get_entry(entry_id)
    if entry is None or entry.domain != DOMAIN:
        raise HomeAssistantError(f"Unknown Agent DVR config entry: {entry_id}")
    return entry


class AgentDVRMediaSource(MediaSource):
    """Browse and resolve Agent DVR recordings."""

    name = "Agent DVR"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the media source."""
        super().__init__(DOMAIN)
        self.hass = hass

    async def async_browse_media(self, item: MediaSourceItem) -> BrowseMediaSource:
        """Browse Agent DVR servers, then their cameras, then recordings."""
        entry_id, _, rest = item.identifier.partition("|")
        camera_key, _, _filename = rest.partition("|")

        if not entry_id:
            return self._browse_servers()
        if not camera_key:
            return await self._browse_cameras(_get_entry(self.hass, entry_id))
        return await self._browse_recordings(
            _get_entry(self.hass, entry_id), camera_key
        )

    def _browse_servers(self) -> BrowseMediaSource:
        entries = self.hass.config_entries.async_entries(DOMAIN)
        children = [
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
        ]
        return BrowseMediaSource(
            domain=DOMAIN,
            identifier="",
            media_class=MediaClass.DIRECTORY,
            media_content_type="",
            title="Agent DVR",
            can_play=False,
            can_expand=True,
            children=children,
            children_media_class=MediaClass.DIRECTORY,
        )

    async def _browse_cameras(self, entry: AgentDVRConfigEntry) -> BrowseMediaSource:
        coordinator = entry.runtime_data.coordinator
        children = [
            BrowseMediaSource(
                domain=DOMAIN,
                identifier=f"{entry.entry_id}|{oid_ot}",
                media_class=MediaClass.DIRECTORY,
                media_content_type="",
                title=device["name"],
                can_play=False,
                can_expand=True,
                children_media_class=MediaClass.VIDEO,
            )
            for oid_ot, device in coordinator.data["devices"].items()
            if device["typeID"] == DEVICE_TYPE_CAMERA
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

    async def _browse_recordings(
        self, entry: AgentDVRConfigEntry, camera_key: str
    ) -> BrowseMediaSource:
        coordinator = entry.runtime_data.coordinator
        device = coordinator.data["devices"].get(camera_key)
        if device is None:
            raise HomeAssistantError(f"Unknown camera: {camera_key}")

        oid, ot_id = int(device["id"]), int(device["typeID"])
        try:
            recordings = await entry.runtime_data.webrtc_pool.run(
                lambda s: s.get_recordings(oid, ot_id, limit=RECORDINGS_LIMIT)
            )
        except AgentDVRWebRTCError as err:
            raise HomeAssistantError(f"Could not load recordings: {err}") from err

        children = [
            BrowseMediaSource(
                domain=DOMAIN,
                identifier=f"{entry.entry_id}|{camera_key}|{rec['fn']}",
                media_class=MediaClass.VIDEO,
                media_content_type=MediaType.VIDEO,
                title=rec["fn"],
                can_play=True,
                can_expand=False,
            )
            for rec in recordings
            if rec.get("fn")
        ]
        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=f"{entry.entry_id}|{camera_key}",
            media_class=MediaClass.DIRECTORY,
            media_content_type="",
            title=device["name"],
            can_play=False,
            can_expand=True,
            children=children,
            children_media_class=MediaClass.VIDEO,
        )

    async def async_resolve_media(self, item: MediaSourceItem) -> PlayMedia:
        """Download (if not already cached) and resolve a recording."""
        entry_id, _, rest = item.identifier.partition("|")
        camera_key, sep, filename = rest.partition("|")
        if not entry_id or not sep:
            raise HomeAssistantError("Invalid media identifier")

        entry = _get_entry(self.hass, entry_id)
        coordinator = entry.runtime_data.coordinator
        device = coordinator.data["devices"].get(camera_key)
        if device is None:
            raise HomeAssistantError(f"Unknown camera: {camera_key}")
        oid, ot_id = int(device["id"]), int(device["typeID"])

        cache_dir = self.hass.config.path("www", DOMAIN, entry.entry_id)
        cache_path = os.path.join(cache_dir, filename)
        mime_type = mimetypes.guess_type(filename)[0] or "video/x-matroska"

        if not await self.hass.async_add_executor_job(os.path.isfile, cache_path):
            try:
                data = await entry.runtime_data.webrtc_pool.run(
                    lambda s: s.download_file(oid, ot_id, filename)
                )
            except AgentDVRWebRTCError as err:
                raise HomeAssistantError(f"Download failed: {err}") from err

            def _write() -> None:
                os.makedirs(cache_dir, exist_ok=True)
                with open(cache_path, "wb") as f:
                    f.write(data)

            await self.hass.async_add_executor_job(_write)
            _LOGGER.debug("Cached %s (%d bytes) at %s", filename, len(data), cache_path)

        rel_path = os.path.relpath(cache_path, self.hass.config.path("www"))
        return PlayMedia(url=f"/local/{rel_path}", mime_type=mime_type)
