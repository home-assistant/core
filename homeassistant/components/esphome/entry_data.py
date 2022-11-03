"""Runtime entry data for ESPHome stored in hass.data."""
from __future__ import annotations

import asyncio
from collections.abc import Callable, MutableMapping
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
from bleak.backends.service import BleakGATTServiceCollection
from lru import LRU  # pylint: disable=no-name-in-module

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.storage import Store

SAVE_DELAY = 120
_LOGGER = logging.getLogger(__name__)

# Mapping from ESPHome info type to HA platform
INFO_TYPE_TO_PLATFORM: dict[type[EntityInfo], str] = {
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
MAX_CACHED_SERVICES = 128


@dataclass
class RuntimeEntryData:
    """Store runtime data for esphome config entries."""

    entry_id: str
    client: APIClient
    store: Store
    state: dict[type[EntityState], dict[int, EntityState]] = field(default_factory=dict)
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
    loaded_platforms: set[str] = field(default_factory=set)
    platform_load_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    _storage_contents: dict[str, Any] | None = None
    ble_connections_free: int = 0
    ble_connections_limit: int = 0
    _ble_connection_free_futures: list[asyncio.Future[int]] = field(
        default_factory=list
    )
    _gatt_services_cache: MutableMapping[int, BleakGATTServiceCollection] = field(
        default_factory=lambda: LRU(MAX_CACHED_SERVICES)  # type: ignore[no-any-return]
    )

    @property
    def name(self) -> str:
        """Return the name of the device."""
        return self.device_info.name if self.device_info else self.entry_id

    def get_gatt_services_cache(
        self, address: int
    ) -> BleakGATTServiceCollection | None:
        """Get the BleakGATTServiceCollection for the given address."""
        return self._gatt_services_cache.get(address)

    def set_gatt_services_cache(
        self, address: int, services: BleakGATTServiceCollection
    ) -> None:
        """Set the BleakGATTServiceCollection for the given address."""
        self._gatt_services_cache[address] = services

    @callback
    def async_update_ble_connection_limits(self, free: int, limit: int) -> None:
        """Update the BLE connection limits."""
        _LOGGER.debug(
            "%s: BLE connection limits: used=%s free=%s limit=%s",
            self.name,
            limit - free,
            free,
            limit,
        )
        self.ble_connections_free = free
        self.ble_connections_limit = limit
        if free:
            for fut in self._ble_connection_free_futures:
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
    def async_remove_entity(
        self, hass: HomeAssistant, component_key: str, key: int
    ) -> None:
        """Schedule the removal of an entity."""
        signal = f"esphome_{self.entry_id}_remove_{component_key}_{key}"
        async_dispatcher_send(hass, signal)

    async def _ensure_platforms_loaded(
        self, hass: HomeAssistant, entry: ConfigEntry, platforms: set[str]
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
        for info in infos:
            for info_type, platform in INFO_TYPE_TO_PLATFORM.items():
                if isinstance(info, info_type):
                    needed_platforms.add(platform)
                    break
        await self._ensure_platforms_loaded(hass, entry, needed_platforms)

        # Then send dispatcher event
        signal = f"esphome_{self.entry_id}_on_list"
        async_dispatcher_send(hass, signal, infos)

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
        subscription_key = (type(state), state.key)
        self.state[type(state)][state.key] = state
        _LOGGER.debug(
            "%s: dispatching update with key %s: %s",
            self.name,
            subscription_key,
            state,
        )
        if subscription_key in self.state_subscriptions:
            self.state_subscriptions[subscription_key]()

    @callback
    def async_update_device_state(self, hass: HomeAssistant) -> None:
        """Distribute an update of a core device state like availability."""
        signal = f"esphome_{self.entry_id}_on_device_update"
        async_dispatcher_send(hass, signal)

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
