"""Expose Shelly camera storage as media sources."""

from operator import itemgetter
from typing import Any, NamedTuple, override
from urllib.parse import urljoin

from aioshelly.exceptions import DeviceConnectionError, InvalidAuthError, RpcCallError

from homeassistant.components.camera import DOMAIN as CAMERA_DOMAIN
from homeassistant.components.media_player import BrowseError, MediaClass, MediaType
from homeassistant.components.media_source import (
    BrowseMediaSource,
    MediaSource,
    MediaSourceItem,
    PlayMedia,
    Unresolvable,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import ShellyConfigEntry, ShellyRpcCoordinator
from .utils import get_device_url

MAX_ITEMS = 500
STORAGE_ID = 0
STORAGE_KEY = f"storage:{STORAGE_ID}"


class MediaKind(NamedTuple):
    """Media class, content type and mime type of a storage item type."""

    media_class: MediaClass
    media_type: MediaType
    mime_type: str


MEDIA_KINDS: dict[str, MediaKind] = {
    "video": MediaKind(MediaClass.VIDEO, MediaType.VIDEO, "video/mp4"),
    "image": MediaKind(MediaClass.IMAGE, MediaType.IMAGE, "image/jpeg"),
}


async def async_get_media_source(hass: HomeAssistant) -> ShellyStorageMediaSource:
    """Set up Shelly storage media source."""
    return ShellyStorageMediaSource(hass)


def _has_active_storage(coordinator: ShellyRpcCoordinator) -> bool:
    """Return true if the device storage is mounted and ready."""
    return bool(coordinator.device.status.get(STORAGE_KEY, {}).get("active"))


class ShellyStorageMediaSource(MediaSource):
    """Provide Shelly camera storage as media sources."""

    name = "Shelly"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize ShellyStorageMediaSource."""
        super().__init__(DOMAIN)
        self.hass = hass

    @override
    async def async_browse_media(self, item: MediaSourceItem) -> BrowseMediaSource:
        """Return media."""
        if not item.identifier:
            return self._async_root()

        entry, items = await self._async_get_items(
            item.identifier, item.identifier, BrowseError
        )
        base_url = get_device_url(entry.data)
        stored_items = sorted(
            (stored for stored in items if stored["type"] in MEDIA_KINDS),
            key=itemgetter("ts"),
            reverse=True,
        )
        return self._async_storage_folder(
            entry,
            [
                self._async_storage_child(entry, stored, base_url)
                for stored in stored_items[:MAX_ITEMS]
            ],
        )

    @override
    async def async_resolve_media(self, item: MediaSourceItem) -> PlayMedia:
        """Resolve media to a url."""
        identifier = item.identifier or ""
        entry_id, _, media_id = identifier.partition(":")
        if not media_id:
            raise Unresolvable(
                translation_domain=DOMAIN,
                translation_key="unexpected_identifier",
                translation_placeholders={"identifier": identifier},
            )
        entry, items = await self._async_get_items(entry_id, identifier, Unresolvable)
        for stored in items:
            if stored["media_id"] == media_id and stored["type"] in MEDIA_KINDS:
                return PlayMedia(
                    url=urljoin(get_device_url(entry.data), stored["url"]),
                    mime_type=MEDIA_KINDS[stored["type"]].mime_type,
                )
        raise Unresolvable(
            translation_domain=DOMAIN,
            translation_key="unexpected_identifier",
            translation_placeholders={"identifier": identifier},
        )

    async def _async_get_items(
        self,
        entry_id: str,
        identifier: str,
        error_cls: type[HomeAssistantError],
    ) -> tuple[ShellyConfigEntry, list[dict[str, Any]]]:
        """Return the config entry and storage items for an entry id."""
        entry: ShellyConfigEntry | None = self.hass.config_entries.async_get_entry(
            entry_id
        )
        if (
            entry is None
            or entry.domain != DOMAIN
            or entry.state is not ConfigEntryState.LOADED
            or (coordinator := entry.runtime_data.rpc) is None
        ):
            raise error_cls(
                translation_domain=DOMAIN,
                translation_key="unexpected_identifier",
                translation_placeholders={"identifier": identifier},
            )
        if not _has_active_storage(coordinator):
            raise error_cls(
                translation_domain=DOMAIN,
                translation_key="storage_unavailable",
                translation_placeholders={"device": entry.title},
            )
        try:
            items = await coordinator.device.get_storage_list(STORAGE_ID)
        except InvalidAuthError as err:
            await coordinator.async_shutdown_device_and_start_reauth()
            raise error_cls(
                translation_domain=DOMAIN,
                translation_key="auth_error",
                translation_placeholders={"device": entry.title},
            ) from err
        except (DeviceConnectionError, RpcCallError) as err:
            raise error_cls(
                translation_domain=DOMAIN,
                translation_key="storage_unavailable",
                translation_placeholders={"device": entry.title},
            ) from err
        return entry, items

    def _async_root(self) -> BrowseMediaSource:
        """Return all Shelly devices with active storage as root browsing structure."""
        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=None,
            media_class=MediaClass.APP,
            media_content_type="",
            title="Shelly",
            can_play=False,
            can_expand=True,
            children=[
                self._async_storage_folder(entry)
                for entry in self.hass.config_entries.async_loaded_entries(DOMAIN)
                if (coordinator := entry.runtime_data.rpc) is not None
                and _has_active_storage(coordinator)
            ],
        )

    def _async_storage_folder(
        self,
        entry: ShellyConfigEntry,
        children: list[BrowseMediaSource] | None = None,
    ) -> BrowseMediaSource:
        """Return BrowseMedia node for device storage."""
        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=entry.entry_id,
            media_class=MediaClass.DIRECTORY,
            media_content_type=MediaType.PLAYLIST,
            title=entry.title,
            thumbnail=self._async_camera_thumbnail(entry.entry_id),
            can_play=False,
            can_expand=True,
            children=children,
        )

    def _async_camera_thumbnail(self, entry_id: str) -> str | None:
        """Return camera proxy thumbnail for a config entry, if available."""
        entity_reg = er.async_get(self.hass)
        for entity in er.async_entries_for_config_entry(entity_reg, entry_id):
            if entity.domain == CAMERA_DOMAIN:
                return f"/api/camera_proxy/{entity.entity_id}"
        return None

    def _async_storage_child(
        self, entry: ShellyConfigEntry, stored: dict[str, Any], base_url: str
    ) -> BrowseMediaSource:
        """Return BrowseMedia node for a single storage item."""
        kind = MEDIA_KINDS[stored["type"]]
        local_time = dt_util.as_local(
            dt_util.utc_from_timestamp(stored["ts"])
        ).strftime("%Y-%m-%d %H:%M:%S")
        trigger = stored.get("trigger") or {}
        title = f"{local_time} · {trigger.get('event', 'manual')}"
        if (duration := stored.get("duration")) is not None:
            title += f" · {duration:g}s"
        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=f"{entry.entry_id}:{stored['media_id']}",
            media_class=kind.media_class,
            media_content_type=kind.media_type,
            title=title,
            thumbnail=(
                urljoin(base_url, thumbnail_url)
                if (thumbnail_url := stored.get("thumbnail_url"))
                else None
            ),
            can_play=True,
            can_expand=False,
        )
