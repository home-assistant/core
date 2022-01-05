"""System Bridge Media Source Implementation."""
from __future__ import annotations

from systembridge import Bridge
from systembridge.objects.filesystem.file import FilesystemFile

from homeassistant.components.media_player.const import MEDIA_CLASS_DIRECTORY
from homeassistant.components.media_source.const import (
    MEDIA_CLASS_MAP,
    MEDIA_MIME_TYPES,
)
from homeassistant.components.media_source.models import (
    BrowseMediaSource,
    MediaSource,
    MediaSourceItem,
    PlayMedia,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import SystemBridgeDataUpdateCoordinator

ROOT_PATHS: list[str] = [
    "desktop",
    "documents",
    "downloads",
    "home",
    "music",
    "pictures",
    "videos",
]


async def async_get_media_source(hass: HomeAssistant):
    """Set up SystemBridge media source."""
    entry: ConfigEntry = hass.config_entries.async_entries(DOMAIN)[0]
    coordinator: SystemBridgeDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    return SystemBridgeSource(hass, entry.title, coordinator.data)


class SystemBridgeSource(MediaSource):
    """Provide System Bridge filesystem files as a media source."""

    def __init__(self, hass: HomeAssistant, name: str, bridge: Bridge) -> None:
        """Initialize SystemBridge source."""
        super().__init__(DOMAIN)

        self.name: str = f"System Bridge - {name}"
        self.hass: HomeAssistant = hass
        self.bridge: Bridge = bridge

    async def async_resolve_media(self, item: MediaSourceItem) -> PlayMedia:
        """Resolve media to a url."""
        path, mime_type = item.identifier.split("~~", 1)
        return PlayMedia(
            self.bridge.get_filesystem_file_data_url(path),
            mime_type,
        )

    async def async_browse_media(self, item: MediaSourceItem) -> BrowseMediaSource:
        """Return media."""
        if not item.identifier:
            return _build_root_paths(self.name)

        return await self._build_media_items(item.identifier)

    async def _build_media_items(self, path: str) -> BrowseMediaSource:
        """Fetch requested files."""
        files: list[FilesystemFile] = await self.bridge.async_get_filesystem_files(path)

        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=path,
            media_class=MEDIA_CLASS_DIRECTORY,
            media_content_type="",
            title=f"{self.name} - {path}",
            can_play=False,
            can_expand=True,
            children=[
                _build_media_item(path, file)
                for file in files
                if file.isDirectory
                or (
                    file.isFile
                    and file.mimeType is not None
                    and file.mimeType.startswith(MEDIA_MIME_TYPES)
                )
            ],
        )


def _build_root_paths(title: str) -> BrowseMediaSource:
    """Build base categories for System Bridge media."""
    return BrowseMediaSource(
        domain=DOMAIN,
        identifier="",
        media_class=MEDIA_CLASS_DIRECTORY,
        media_content_type="",
        title=title,
        can_play=False,
        can_expand=True,
        children=[
            BrowseMediaSource(
                domain=DOMAIN,
                identifier=source,
                media_class=MEDIA_CLASS_DIRECTORY,
                media_content_type="",
                title=source,
                can_play=False,
                can_expand=True,
                children=[],
                children_media_class=MEDIA_CLASS_DIRECTORY,
            )
            for source in ROOT_PATHS
        ],
        children_media_class=MEDIA_CLASS_DIRECTORY,
    )


def _build_media_item(path: str, file: FilesystemFile) -> BrowseMediaSource:
    """Build individual media item."""
    ext = f"~~{file.mimeType}" if file.isFile and file.mimeType is not None else ""
    return BrowseMediaSource(
        domain=DOMAIN,
        identifier=f"{path}/{file.name}{ext}",
        media_class=MEDIA_CLASS_DIRECTORY
        if file.isDirectory or file.mimeType is None
        else MEDIA_CLASS_MAP[file.mimeType.split("/", 1)[0]],
        media_content_type=file.mimeType,
        title=file.name,
        can_play=file.isFile,
        can_expand=file.isDirectory,
    )
