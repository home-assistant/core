"""Expose Shelly camera storage as media sources."""

from typing import Any, cast, override

from aioshelly.const import MODEL_CAMERA
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
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_MODEL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import ShellyConfigEntry, ShellyRpcCoordinator
from .utils import get_host, get_http_port

MAX_ITEMS = 500
DEFAULT_STORAGE_ID = 0

VIDEO_MIME_TYPE = "video/mp4"
IMAGE_MIME_TYPE = "image/jpeg"


async def async_get_media_source(hass: HomeAssistant) -> ShellyStorageMediaSource:
    """Set up Shelly storage media source."""
    return ShellyStorageMediaSource(hass)


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

        parts = item.identifier.split(":")
        if len(parts) != 2:
            raise BrowseError(
                translation_domain=DOMAIN,
                translation_key="unexpected_identifier",
                translation_placeholders={"identifier": item.identifier},
            )
        entry_id, storage_id = parts
        if (result := self._get_rpc_coordinator(entry_id)) is None:
            raise BrowseError(
                translation_domain=DOMAIN,
                translation_key="unexpected_identifier",
                translation_placeholders={"identifier": item.identifier},
            )
        entry, coordinator = result
        try:
            storage = int(storage_id)
        except ValueError as err:
            raise BrowseError(
                translation_domain=DOMAIN,
                translation_key="unexpected_identifier",
                translation_placeholders={"identifier": item.identifier},
            ) from err
        return await self._async_browse_storage(
            entry, coordinator, storage, item.identifier
        )

    @override
    async def async_resolve_media(self, item: MediaSourceItem) -> PlayMedia:
        """Resolve media to a url."""
        parts = (item.identifier or "").split(":")
        if len(parts) != 3:
            raise Unresolvable(
                translation_domain=DOMAIN,
                translation_key="unexpected_identifier",
                translation_placeholders={"identifier": item.identifier},
            )
        entry_id, storage_id, media_id = parts
        if (result := self._get_rpc_coordinator(entry_id)) is None:
            raise Unresolvable(
                translation_domain=DOMAIN,
                translation_key="unexpected_identifier",
                translation_placeholders={"identifier": item.identifier},
            )
        entry, coordinator = result
        try:
            storage = int(storage_id)
        except ValueError as err:
            raise Unresolvable(
                translation_domain=DOMAIN,
                translation_key="unexpected_identifier",
                translation_placeholders={"identifier": item.identifier},
            ) from err
        if coordinator.device.status.get("camera:0", {}).get("privacy"):
            raise Unresolvable(
                translation_domain=DOMAIN,
                translation_key="storage_private",
                translation_placeholders={"device": entry.title},
            )
        try:
            items = await self._async_fetch_items(coordinator, storage)
        except InvalidAuthError as err:
            raise Unresolvable(
                translation_domain=DOMAIN,
                translation_key="auth_error",
                translation_placeholders={"device": entry.title},
            ) from err
        except (DeviceConnectionError, RpcCallError) as err:
            raise Unresolvable(
                translation_domain=DOMAIN,
                translation_key="storage_unavailable",
                translation_placeholders={"device": entry.title},
            ) from err
        for stored in items:
            if stored.get("media_id") != media_id or not stored.get("url"):
                continue
            if stored.get("type") == "video":
                return PlayMedia(url=stored["url"], mime_type=VIDEO_MIME_TYPE)
            if stored.get("type") == "image":
                return PlayMedia(url=stored["url"], mime_type=IMAGE_MIME_TYPE)
        raise Unresolvable(
            translation_domain=DOMAIN,
            translation_key="unexpected_identifier",
            translation_placeholders={"identifier": item.identifier},
        )

    def _get_rpc_coordinator(
        self, entry_id: str
    ) -> tuple[ShellyConfigEntry, ShellyRpcCoordinator] | None:
        """Return config entry and RPC coordinator for an entry id."""
        if (entry := self.hass.config_entries.async_get_entry(entry_id)) is None:
            return None
        if entry.domain != DOMAIN or not hasattr(entry, "runtime_data"):
            return None
        shelly_entry = cast(ShellyConfigEntry, entry)
        if (rpc := shelly_entry.runtime_data.rpc) is None:
            return None
        return (shelly_entry, rpc)

    def _is_camera_entry(self, entry: ConfigEntry) -> bool:
        """Return true if the entry is a loaded RPC camera device."""
        if entry.domain != DOMAIN or not hasattr(entry, "runtime_data"):
            return False
        rpc = cast(ShellyConfigEntry, entry).runtime_data.rpc
        if rpc is None:
            return False
        if entry.data.get(CONF_MODEL) == MODEL_CAMERA:
            return True
        return "camera:0" in rpc.device.status

    def _async_root(self) -> BrowseMediaSource:
        """Return all available Shelly cameras as root browsing structure."""
        children: list[BrowseMediaSource] = []
        for entry in self.hass.config_entries.async_loaded_entries(DOMAIN):
            if not self._is_camera_entry(entry):
                continue
            children.append(
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier=f"{entry.entry_id}:{DEFAULT_STORAGE_ID}",
                    media_class=MediaClass.DIRECTORY,
                    media_content_type=MediaType.PLAYLIST,
                    title=entry.title,
                    thumbnail=self._async_camera_thumbnail(entry.entry_id),
                    can_play=False,
                    can_expand=True,
                )
            )
        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=None,
            media_class=MediaClass.APP,
            media_content_type="",
            title="Shelly",
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

    async def _async_browse_storage(
        self,
        entry: ShellyConfigEntry,
        coordinator: ShellyRpcCoordinator,
        storage_id: int,
        identifier: str,
    ) -> BrowseMediaSource:
        """Return BrowseMedia tree for camera storage."""
        if coordinator.device.status.get("camera:0", {}).get("privacy"):
            raise BrowseError(
                translation_domain=DOMAIN,
                translation_key="storage_private",
                translation_placeholders={"device": entry.title},
            )
        try:
            items = await self._async_fetch_items(coordinator, storage_id)
        except InvalidAuthError as err:
            raise BrowseError(
                translation_domain=DOMAIN,
                translation_key="auth_error",
                translation_placeholders={"device": entry.title},
            ) from err
        except (DeviceConnectionError, RpcCallError) as err:
            raise BrowseError(
                translation_domain=DOMAIN,
                translation_key="storage_unavailable",
                translation_placeholders={"device": entry.title},
            ) from err
        base_url = self._async_base_url(entry)
        children = [
            child
            for stored in sorted(
                items, key=lambda item: item.get("ts", 0), reverse=True
            )[:MAX_ITEMS]
            if (child := self._async_storage_child(entry, storage_id, stored, base_url))
            is not None
        ]
        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=identifier,
            media_class=MediaClass.DIRECTORY,
            media_content_type=MediaType.PLAYLIST,
            title=entry.title,
            thumbnail=self._async_camera_thumbnail(entry.entry_id),
            can_play=False,
            can_expand=True,
            children=children,
        )

    def _async_storage_child(
        self,
        entry: ShellyConfigEntry,
        storage_id: int,
        stored: dict[str, Any],
        base_url: str,
    ) -> BrowseMediaSource | None:
        """Return BrowseMedia node for a single storage item."""
        if stored.get("type") == "video":
            media_class = MediaClass.VIDEO
            media_content_type: str = MediaType.VIDEO
        elif stored.get("type") == "image":
            media_class = MediaClass.IMAGE
            media_content_type = IMAGE_MIME_TYPE
        else:
            return None
        if not stored.get("media_id") or not stored.get("url"):
            return None
        local_time = dt_util.as_local(
            dt_util.utc_from_timestamp(stored["ts"])
        ).strftime("%Y-%m-%d %H:%M:%S")
        trigger = stored.get("trigger") or {}
        title = f"{local_time} · {trigger.get('event', 'manual')}"
        if (duration := stored.get("duration")) is not None:
            title += f" · {duration:g}s"
        thumbnail = None
        if thumb := stored.get("thumbnail_url"):
            if thumb.startswith("http"):
                thumbnail = thumb
            elif thumb.startswith("/"):
                thumbnail = f"{base_url}{thumb}"
        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=f"{entry.entry_id}:{storage_id}:{stored['media_id']}",
            media_class=media_class,
            media_content_type=media_content_type,
            title=title,
            thumbnail=thumbnail,
            can_play=True,
            can_expand=False,
        )

    def _async_base_url(self, entry: ShellyConfigEntry) -> str:
        """Return base URL for relative storage thumbnail URLs."""
        host = get_host(entry.data[CONF_HOST])
        if (port := get_http_port(entry.data)) == 80:
            return f"http://{host}"
        return f"http://{host}:{port}"

    async def _async_fetch_items(
        self, coordinator: ShellyRpcCoordinator, storage_id: int
    ) -> list[dict[str, Any]]:
        """Fetch all storage items from the device."""
        try:
            return await coordinator.device.get_storage_list(storage_id)
        except InvalidAuthError:
            await coordinator.async_shutdown_device_and_start_reauth()
            raise
