"""Runtime entry data for ESPHome stored in hass.data."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Callable, cast

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
    NumberInfo,
    SelectInfo,
    SensorInfo,
    SwitchInfo,
    TextSensorInfo,
    UserService,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.storage import Store

SAVE_DELAY = 120

# Mapping from ESPHome info type to HA platform
INFO_TYPE_TO_PLATFORM: dict[type[EntityInfo], str] = {
    BinarySensorInfo: "binary_sensor",
    CameraInfo: "camera",
    ClimateInfo: "climate",
    CoverInfo: "cover",
    FanInfo: "fan",
    LightInfo: "light",
    NumberInfo: "number",
    SelectInfo: "select",
    SensorInfo: "sensor",
    SwitchInfo: "switch",
    TextSensorInfo: "sensor",
}


@dataclass
class RuntimeEntryData:
    """Store runtime data for esphome config entries."""

    entry_id: str
    client: APIClient
    store: Store
    state: dict[str, dict[int, EntityState]] = field(default_factory=dict)
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
    loaded_platforms: set[str] = field(default_factory=set)
    platform_load_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    _storage_contents: dict[str, Any] | None = None

    @callback
    def async_update_entity(
        self, hass: HomeAssistant, component_key: str, key: int
    ) -> None:
        """Schedule the update of an entity."""
        signal = f"esphome_{self.entry_id}_update_{component_key}_{key}"
        async_dispatcher_send(hass, signal)

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
            tasks = []
            for platform in needed:
                tasks.append(
                    hass.config_entries.async_forward_entry_setup(entry, platform)
                )
            if tasks:
                await asyncio.wait(tasks)
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
    def async_update_state(self, hass: HomeAssistant, state: EntityState) -> None:
        """Distribute an update of state information to all platforms."""
        signal = f"esphome_{self.entry_id}_on_state"
        async_dispatcher_send(hass, signal, state)

    @callback
    def async_update_device_state(self, hass: HomeAssistant) -> None:
        """Distribute an update of a core device state like availability."""
        signal = f"esphome_{self.entry_id}_on_device_update"
        async_dispatcher_send(hass, signal)

    async def async_load_from_store(self) -> tuple[list[EntityInfo], list[UserService]]:
        """Load the retained data from store and return de-serialized data."""
        restored = await self.store.async_load()
        if restored is None:
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
