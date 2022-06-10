"""System Bridge Media Source Implementation."""
from __future__ import annotations

import asyncio

import async_timeout
from systembridgeconnector.models.media_directories import MediaDirectories
from systembridgeconnector.models.media_files import File as MediaFile

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
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import SystemBridgeDataUpdateCoordinator


async def async_get_media_source(hass: HomeAssistant) -> MediaSource:
    """Set up SystemBridge media source."""
    return SystemBridgeSource(hass)


class SystemBridgeSource(MediaSource):
    """Provide System Bridge media files as a media source."""

    def __init__(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Initialize source."""
        super().__init__(DOMAIN)
        self.name = "System Bridge"
        self.hass: HomeAssistant = hass

    async def async_resolve_media(
        self,
        item: MediaSourceItem,
    ) -> PlayMedia:
        """Resolve media to a url."""
        entry_id, path, mime_type = item.identifier.split("~~", 2)
        entry = self.hass.config_entries.async_get_entry(entry_id)
        if entry is None:
            raise ValueError("Invalid entry")
        path_split = path.split("/", 1)
        return PlayMedia(
            f"{_build_base_url(entry)}&base={path_split[0]}&path={path_split[1]}",
            mime_type,
        )

    async def async_browse_media(
        self,
        item: MediaSourceItem,
    ) -> BrowseMediaSource:
        """Return media."""
        if not item.identifier:
            return self._build_bridges()

        if "~~" not in item.identifier:
            entry = self.hass.config_entries.async_get_entry(item.identifier)
            if entry is None:
                raise ValueError("Invalid entry")
            coordinator: SystemBridgeDataUpdateCoordinator = self.hass.data[DOMAIN].get(
                entry.entry_id
            )
            await coordinator.async_get_media_directories()

            async with async_timeout.timeout(20):
                while coordinator.data.media_directories is None:
                    await asyncio.sleep(1)

            return _build_root_paths(entry, coordinator.data.media_directories)

        entry_id, path = item.identifier.split("~~", 1)
        entry = self.hass.config_entries.async_get_entry(entry_id)
        if entry is None:
            raise ValueError("Invalid entry")

        coordinator = self.hass.data[DOMAIN].get(entry.entry_id)

        path_split = path.split("/", 1)

        await coordinator.async_get_media_files(
            path_split[0], path_split[1] if len(path_split) > 1 else None
        )

        async with async_timeout.timeout(20):
            while coordinator.data.media_files is None:
                await asyncio.sleep(1)

        return _build_media_items(entry, coordinator, path, item.identifier)

    def _build_bridges(self) -> BrowseMediaSource:
        """Build bridges for System Bridge media."""
        children = []
        for entry in self.hass.config_entries.async_entries(DOMAIN):
            if entry.entry_id is not None:
                children.append(
                    BrowseMediaSource(
                        domain=DOMAIN,
                        identifier=entry.entry_id,
                        media_class=MEDIA_CLASS_DIRECTORY,
                        media_content_type="",
                        title=entry.title,
                        can_play=False,
                        can_expand=True,
                        children=[],
                        children_media_class=MEDIA_CLASS_DIRECTORY,
                    )
                )

        return BrowseMediaSource(
            domain=DOMAIN,
            identifier="",
            media_class=MEDIA_CLASS_DIRECTORY,
            media_content_type="",
            title=self.name,
            can_play=False,
            can_expand=True,
            children=children,
            children_media_class=MEDIA_CLASS_DIRECTORY,
        )


def _build_base_url(
    entry: ConfigEntry,
) -> str:
    """Build base url for System Bridge media."""
    return f"http://{entry.data[CONF_HOST]}:{entry.data[CONF_PORT]}/api/media/file/data?apiKey={entry.data[CONF_API_KEY]}"


def _build_root_paths(
    entry: ConfigEntry,
    media_directories: MediaDirectories,
) -> BrowseMediaSource:
    """Build base categories for System Bridge media."""
    return BrowseMediaSource(
        domain=DOMAIN,
        identifier="",
        media_class=MEDIA_CLASS_DIRECTORY,
        media_content_type="",
        title=entry.title,
        can_play=False,
        can_expand=True,
        children=[
            BrowseMediaSource(
                domain=DOMAIN,
                identifier=f"{entry.entry_id}~~{directory.key}",
                media_class=MEDIA_CLASS_DIRECTORY,
                media_content_type="",
                title=f"{directory.key[:1].capitalize()}{directory.key[1:]}",
                can_play=False,
                can_expand=True,
                children=[],
                children_media_class=MEDIA_CLASS_DIRECTORY,
            )
            for directory in media_directories.directories
        ],
        children_media_class=MEDIA_CLASS_DIRECTORY,
    )


def _build_media_items(
    entry: ConfigEntry,
    coordinator: SystemBridgeDataUpdateCoordinator,
    path: str,
    identifier: str,
) -> BrowseMediaSource:
    """Fetch requested files."""
    return BrowseMediaSource(
        domain=DOMAIN,
        identifier=identifier,
        media_class=MEDIA_CLASS_DIRECTORY,
        media_content_type="",
        title=f"{entry.title} - {path}",
        can_play=False,
        can_expand=True,
        children=[
            _build_media_item(identifier, file)
            for file in coordinator.data.media_files.files
            if file.is_directory
            or (
                file.is_file
                and file.mime_type is not None
                and file.mime_type.startswith(MEDIA_MIME_TYPES)
            )
        ],
    )


def _build_media_item(
    path: str,
    file: MediaFile,
) -> BrowseMediaSource:
    """Build individual media item."""
    ext = f"~~{file.mime_type}" if file.is_file and file.mime_type is not None else ""
    return BrowseMediaSource(
        domain=DOMAIN,
        identifier=f"{path}/{file.name}{ext}",
        media_class=MEDIA_CLASS_DIRECTORY
        if file.is_directory or file.mime_type is None
        else MEDIA_CLASS_MAP[file.mime_type.split("/", 1)[0]],
        media_content_type=file.mime_type,
        title=file.name,
        can_play=file.is_file,
        can_expand=file.is_directory,
    )
