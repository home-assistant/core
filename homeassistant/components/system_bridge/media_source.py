"""System Bridge Media Source Implementation."""

from __future__ import annotations

from systembridgemodels.media_directories import MediaDirectory
from systembridgemodels.media_files import MediaFile, MediaFiles
from systembridgemodels.media_get_files import MediaGetFiles

from homeassistant.components.media_player import MediaClass
from homeassistant.components.media_source import (
    MEDIA_CLASS_MAP,
    MEDIA_MIME_TYPES,
    BrowseMediaSource,
    MediaSource,
    MediaSourceItem,
    PlayMedia,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TOKEN
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
            directories = await coordinator.websocket_client.get_directories()
            return _build_root_paths(entry, directories)

        entry_id, path = item.identifier.split("~~", 1)
        entry = self.hass.config_entries.async_get_entry(entry_id)
        if entry is None:
            raise ValueError("Invalid entry")

        coordinator = self.hass.data[DOMAIN].get(entry.entry_id)

        path_split = path.split("/", 1)

        files = await coordinator.websocket_client.get_files(
            MediaGetFiles(
                base=path_split[0],
                path=path_split[1] if len(path_split) > 1 else None,
            )
        )

        return _build_media_items(entry, files, path, item.identifier)

    def _build_bridges(self) -> BrowseMediaSource:
        """Build bridges for System Bridge media."""
        children = [
            BrowseMediaSource(
                domain=DOMAIN,
                identifier=entry.entry_id,
                media_class=MediaClass.DIRECTORY,
                media_content_type="",
                title=entry.title,
                can_play=False,
                can_expand=True,
                children=[],
                children_media_class=MediaClass.DIRECTORY,
            )
            for entry in self.hass.config_entries.async_entries(DOMAIN)
            if entry.entry_id is not None
        ]

        return BrowseMediaSource(
            domain=DOMAIN,
            identifier="",
            media_class=MediaClass.DIRECTORY,
            media_content_type="",
            title=self.name,
            can_play=False,
            can_expand=True,
            children=children,
            children_media_class=MediaClass.DIRECTORY,
        )


def _build_base_url(
    entry: ConfigEntry,
) -> str:
    """Build base url for System Bridge media."""
    return (
        f"http://{entry.data[CONF_HOST]}:{entry.data[CONF_PORT]}"
        f"/api/media/file/data?token={entry.data[CONF_TOKEN]}"
    )


def _build_root_paths(
    entry: ConfigEntry,
    media_directories: list[MediaDirectory],
) -> BrowseMediaSource:
    """Build base categories for System Bridge media."""
    return BrowseMediaSource(
        domain=DOMAIN,
        identifier="",
        media_class=MediaClass.DIRECTORY,
        media_content_type="",
        title=entry.title,
        can_play=False,
        can_expand=True,
        children=[
            BrowseMediaSource(
                domain=DOMAIN,
                identifier=f"{entry.entry_id}~~{directory.key}",
                media_class=MediaClass.DIRECTORY,
                media_content_type="",
                title=f"{directory.key[:1].capitalize()}{directory.key[1:]}",
                can_play=False,
                can_expand=True,
                children=[],
                children_media_class=MediaClass.DIRECTORY,
            )
            for directory in media_directories
        ],
        children_media_class=MediaClass.DIRECTORY,
    )


def _build_media_items(
    entry: ConfigEntry,
    media_files: MediaFiles,
    path: str,
    identifier: str,
) -> BrowseMediaSource:
    """Fetch requested files."""
    return BrowseMediaSource(
        domain=DOMAIN,
        identifier=identifier,
        media_class=MediaClass.DIRECTORY,
        media_content_type="",
        title=f"{entry.title} - {path}",
        can_play=False,
        can_expand=True,
        children=[
            _build_media_item(identifier, file)
            for file in media_files.files
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
    media_file: MediaFile,
) -> BrowseMediaSource:
    """Build individual media item."""
    ext = ""
    if media_file.is_file and media_file.mime_type is not None:
        ext = f"~~{media_file.mime_type}"

    if media_file.is_directory or media_file.mime_type is None:
        media_class = MediaClass.DIRECTORY
    else:
        media_class = MEDIA_CLASS_MAP[media_file.mime_type.split("/", 1)[0]]

    return BrowseMediaSource(
        domain=DOMAIN,
        identifier=f"{path}/{media_file.name}{ext}",
        media_class=media_class,
        media_content_type=media_file.mime_type,
        title=media_file.name,
        can_play=media_file.is_file,
        can_expand=media_file.is_directory,
    )
