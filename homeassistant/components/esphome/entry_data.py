"""Runtime entry data for ESPHome stored in hass.data."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
import logging
from typing import Any, cast

from aioesphomeapi import (
    COMPONENT_TYPE_TO_INFO,
    APIClient,
    APIVersion,
    BinarySensorInfo,
    CameraInfo,
    ClimateInfo,
    CoverInfo,
    DeviceInfo,
    EntityInfo,
    EntityState,
    FanInfo,
    LightInfo,
    LockInfo,
    MediaPlayerInfo,
    NumberInfo,
    SelectInfo,
    SensorInfo,
    SwitchInfo,
    TextSensorInfo,
    UserService,
)
from aioesphomeapi.model import ButtonInfo

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.storage import Store

from .dashboard import async_get_dashboard

_SENTINEL = object()
SAVE_DELAY = 120
_LOGGER = logging.getLogger(__name__)

# Mapping from ESPHome info type to HA platform
INFO_TYPE_TO_PLATFORM: dict[type[EntityInfo], Platform] = {
    BinarySensorInfo: Platform.BINARY_SENSOR,
    ButtonInfo: Platform.BUTTON,
    CameraInfo: Platform.CAMERA,
    ClimateInfo: Platform.CLIMATE,
    CoverInfo: Platform.COVER,
    FanInfo: Platform.FAN,
    LightInfo: Platform.LIGHT,
    LockInfo: Platform.LOCK,
    MediaPlayerInfo: Platform.MEDIA_PLAYER,
    NumberInfo: Platform.NUMBER,
    SelectInfo: Platform.SELECT,
    SensorInfo: Platform.SENSOR,
    SwitchInfo: Platform.SWITCH,
    TextSensorInfo: Platform.SENSOR,
}


@dataclass
class RuntimeEntryData:
    """Store runtime data for esphome config entries."""

    entry_id: str
    client: APIClient
    store: Store
    state: dict[type[EntityState], dict[int, EntityState]] = field(default_factory=dict)
    # When the disconnect callback is called, we mark all states
    # as stale so we will always dispatch a state update when the
    # device reconnects. This is the same format as state_subscriptions.
    stale_state: set[tuple[type[EntityState], int]] = field(default_factory=set)
    info: dict[str, dict[int, EntityInfo]] = field(default_factory=dict)

    # A second list of EntityInfo objects
    # This is necessary for when an entity is being removed. HA requires
    # some static info to be accessible during removal (unique_id, maybe others)
    # If an entity can't find anything in the info array, it will look for info here.
    old_info: dict[str, dict[int, EntityInfo]] = field(default_factory=dict)

    services: dict[int, UserService] = field(default_factory=dict)
    available: bool = False
    device_info: DeviceInfo | None = None
    api_version: APIVersion = field(default_factory=APIVersion)
    cleanup_callbacks: list[Callable[[], None]] = field(default_factory=list)
    disconnect_callbacks: list[Callable[[], None]] = field(default_factory=list)
    state_subscriptions: dict[
        tuple[type[EntityState], int], Callable[[], None]
    ] = field(default_factory=dict)
    loaded_platforms: set[Platform] = field(default_factory=set)
    platform_load_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    _storage_contents: dict[str, Any] | None = None
    ble_connections_free: int = 0
    ble_connections_limit: int = 0
    _ble_connection_free_futures: list[asyncio.Future[int]] = field(
        default_factory=list
    )
    assist_pipeline_update_callbacks: list[Callable[[], None]] = field(
        default_factory=list
    )
    assist_pipeline_state: bool = False

    @property
    def name(self) -> str:
        """Return the name of the device."""
        return self.device_info.name if self.device_info else self.entry_id

    @property
    def friendly_name(self) -> str:
        """Return the friendly name of the device."""
        if self.device_info and self.device_info.friendly_name:
            return self.device_info.friendly_name
        return self.name

    @property
    def signal_device_updated(self) -> str:
        """Return the signal to listen to for core device state update."""
        return f"esphome_{self.entry_id}_on_device_update"

    @property
    def signal_static_info_updated(self) -> str:
        """Return the signal to listen to for updates on static info."""
        return f"esphome_{self.entry_id}_on_list"

    @callback
    def async_update_ble_connection_limits(self, free: int, limit: int) -> None:
        """Update the BLE connection limits."""
        _LOGGER.debug(
            "%s [%s]: BLE connection limits: used=%s free=%s limit=%s",
            self.name,
            self.device_info.mac_address if self.device_info else "unknown",
            limit - free,
            free,
            limit,
        )
        self.ble_connections_free = free
        self.ble_connections_limit = limit
        if not free:
            return
        for fut in self._ble_connection_free_futures:
            # If wait_for_ble_connections_free gets cancelled, it will
            # leave a future in the list. We need to check if it's done
            # before setting the result.
            if not fut.done():
                fut.set_result(free)
        self._ble_connection_free_futures.clear()

    async def wait_for_ble_connections_free(self) -> int:
        """Wait until there are free BLE connections."""
        if self.ble_connections_free > 0:
            return self.ble_connections_free
        fut: asyncio.Future[int] = asyncio.Future()
        self._ble_connection_free_futures.append(fut)
        return await fut

    @callback
    def async_set_assist_pipeline_state(self, state: bool) -> None:
        """Set the assist pipeline state."""
        self.assist_pipeline_state = state
        for update_callback in self.assist_pipeline_update_callbacks:
            update_callback()

    def async_subscribe_assist_pipeline_update(
        self, update_callback: Callable[[], None]
    ) -> Callable[[], None]:
        """Subscribe to assist pipeline updates."""

        def _unsubscribe() -> None:
            self.assist_pipeline_update_callbacks.remove(update_callback)

        self.assist_pipeline_update_callbacks.append(update_callback)
        return _unsubscribe

    @callback
    def async_remove_entity(
        self, hass: HomeAssistant, component_key: str, key: int
    ) -> None:
        """Schedule the removal of an entity."""
        signal = f"esphome_{self.entry_id}_remove_{component_key}_{key}"
        async_dispatcher_send(hass, signal)

    async def _ensure_platforms_loaded(
        self, hass: HomeAssistant, entry: ConfigEntry, platforms: set[Platform]
    ) -> None:
        async with self.platform_load_lock:
            needed = platforms - self.loaded_platforms
            if needed:
                await hass.config_entries.async_forward_entry_setups(entry, needed)
            self.loaded_platforms |= needed

    async def async_update_static_infos(
        self, hass: HomeAssistant, entry: ConfigEntry, infos: list[EntityInfo]
    ) -> None:
        """Distribute an update of static infos to all platforms."""
        # First, load all platforms
        needed_platforms = set()

        if async_get_dashboard(hass):
            needed_platforms.add(Platform.UPDATE)

        if self.device_info is not None and self.device_info.voice_assistant_version:
            needed_platforms.add(Platform.BINARY_SENSOR)
            needed_platforms.add(Platform.SELECT)

        for info in infos:
            for info_type, platform in INFO_TYPE_TO_PLATFORM.items():
                if isinstance(info, info_type):
                    needed_platforms.add(platform)
                    break
        await self._ensure_platforms_loaded(hass, entry, needed_platforms)

        # Then send dispatcher event
        async_dispatcher_send(hass, self.signal_static_info_updated, infos)

    @callback
    def async_subscribe_state_update(
        self,
        state_type: type[EntityState],
        state_key: int,
        entity_callback: Callable[[], None],
    ) -> Callable[[], None]:
        """Subscribe to state updates."""

        def _unsubscribe() -> None:
            self.state_subscriptions.pop((state_type, state_key))

        self.state_subscriptions[(state_type, state_key)] = entity_callback
        return _unsubscribe

    @callback
    def async_update_state(self, state: EntityState) -> None:
        """Distribute an update of state information to the target."""
        key = state.key
        state_type = type(state)
        stale_state = self.stale_state
        current_state_by_type = self.state[state_type]
        current_state = current_state_by_type.get(key, _SENTINEL)
        subscription_key = (state_type, key)
        if current_state == state and subscription_key not in stale_state:
            _LOGGER.debug(
                "%s: ignoring duplicate update with and key %s: %s",
                self.name,
                key,
                state,
            )
            return
        _LOGGER.debug(
            "%s: dispatching update with key %s: %s",
            self.name,
            key,
            state,
        )
        stale_state.discard(subscription_key)
        current_state_by_type[key] = state
        if subscription_key in self.state_subscriptions:
            self.state_subscriptions[subscription_key]()

    @callback
    def async_update_device_state(self, hass: HomeAssistant) -> None:
        """Distribute an update of a core device state like availability."""
        async_dispatcher_send(hass, self.signal_device_updated)

    async def async_load_from_store(self) -> tuple[list[EntityInfo], list[UserService]]:
        """Load the retained data from store and return de-serialized data."""
        if (restored := await self.store.async_load()) is None:
            return [], []
        restored = cast("dict[str, Any]", restored)
        self._storage_contents = restored.copy()

        self.device_info = DeviceInfo.from_dict(restored.pop("device_info"))
        self.api_version = APIVersion.from_dict(restored.pop("api_version", {}))
        infos = []
        for comp_type, restored_infos in restored.items():
            if comp_type not in COMPONENT_TYPE_TO_INFO:
                continue
            for info in restored_infos:
                cls = COMPONENT_TYPE_TO_INFO[comp_type]
                infos.append(cls.from_dict(info))
        services = []
        for service in restored.get("services", []):
            services.append(UserService.from_dict(service))
        return infos, services

    async def async_save_to_store(self) -> None:
        """Generate dynamic data to store and save it to the filesystem."""
        if self.device_info is None:
            raise ValueError("device_info is not set yet")
        store_data: dict[str, Any] = {
            "device_info": self.device_info.to_dict(),
            "services": [],
            "api_version": self.api_version.to_dict(),
        }

        for comp_type, infos in self.info.items():
            store_data[comp_type] = [info.to_dict() for info in infos.values()]
        for service in self.services.values():
            store_data["services"].append(service.to_dict())

        if store_data == self._storage_contents:
            return

        def _memorized_storage() -> dict[str, Any]:
            self._storage_contents = store_data
            return store_data

        self.store.async_delay_save(_memorized_storage, SAVE_DELAY)
