"""Runtime entry data for ESPHome stored in hass.data."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from functools import partial
import logging
from typing import TYPE_CHECKING, Any, Final, TypedDict, cast

from aioesphomeapi import (
    COMPONENT_TYPE_TO_INFO,
    AlarmControlPanelInfo,
    APIClient,
    APIVersion,
    BinarySensorInfo,
    CameraInfo,
    CameraState,
    ClimateInfo,
    CoverInfo,
    DateInfo,
    DateTimeInfo,
    DeviceInfo,
    EntityInfo,
    EntityState,
    Event,
    EventInfo,
    FanInfo,
    LightInfo,
    LockInfo,
    MediaPlayerInfo,
    NumberInfo,
    SelectInfo,
    SensorInfo,
    SensorState,
    SwitchInfo,
    TextInfo,
    TextSensorInfo,
    TimeInfo,
    UpdateInfo,
    UserService,
    ValveInfo,
    build_unique_id,
)
from aioesphomeapi.model import ButtonInfo
from bleak_esphome.backend.device import ESPHomeBluetoothDevice

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.storage import Store

from .const import DOMAIN
from .dashboard import async_get_dashboard

type ESPHomeConfigEntry = ConfigEntry[RuntimeEntryData]


INFO_TO_COMPONENT_TYPE: Final = {v: k for k, v in COMPONENT_TYPE_TO_INFO.items()}

_SENTINEL = object()
SAVE_DELAY = 120
_LOGGER = logging.getLogger(__name__)

# Mapping from ESPHome info type to HA platform
INFO_TYPE_TO_PLATFORM: dict[type[EntityInfo], Platform] = {
    AlarmControlPanelInfo: Platform.ALARM_CONTROL_PANEL,
    BinarySensorInfo: Platform.BINARY_SENSOR,
    ButtonInfo: Platform.BUTTON,
    CameraInfo: Platform.CAMERA,
    ClimateInfo: Platform.CLIMATE,
    CoverInfo: Platform.COVER,
    DateInfo: Platform.DATE,
    DateTimeInfo: Platform.DATETIME,
    EventInfo: Platform.EVENT,
    FanInfo: Platform.FAN,
    LightInfo: Platform.LIGHT,
    LockInfo: Platform.LOCK,
    MediaPlayerInfo: Platform.MEDIA_PLAYER,
    NumberInfo: Platform.NUMBER,
    SelectInfo: Platform.SELECT,
    SensorInfo: Platform.SENSOR,
    SwitchInfo: Platform.SWITCH,
    TextInfo: Platform.TEXT,
    TextSensorInfo: Platform.SENSOR,
    TimeInfo: Platform.TIME,
    UpdateInfo: Platform.UPDATE,
    ValveInfo: Platform.VALVE,
}


class StoreData(TypedDict, total=False):
    """ESPHome storage data."""

    device_info: dict[str, Any]
    services: list[dict[str, Any]]
    api_version: dict[str, Any]


class ESPHomeStorage(Store[StoreData]):
    """ESPHome Storage."""


@dataclass(slots=True)
class RuntimeEntryData:
    """Store runtime data for esphome config entries."""

    entry_id: str
    title: str
    client: APIClient
    store: ESPHomeStorage
    state: dict[type[EntityState], dict[int, EntityState]] = field(default_factory=dict)
    # When the disconnect callback is called, we mark all states
    # as stale so we will always dispatch a state update when the
    # device reconnects. This is the same format as state_subscriptions.
    stale_state: set[tuple[type[EntityState], int]] = field(default_factory=set)
    info: dict[type[EntityInfo], dict[int, EntityInfo]] = field(default_factory=dict)
    services: dict[int, UserService] = field(default_factory=dict)
    available: bool = False
    expected_disconnect: bool = False  # Last disconnect was expected (e.g. deep sleep)
    device_info: DeviceInfo | None = None
    bluetooth_device: ESPHomeBluetoothDevice | None = None
    api_version: APIVersion = field(default_factory=APIVersion)
    cleanup_callbacks: list[CALLBACK_TYPE] = field(default_factory=list)
    disconnect_callbacks: set[CALLBACK_TYPE] = field(default_factory=set)
    state_subscriptions: dict[tuple[type[EntityState], int], CALLBACK_TYPE] = field(
        default_factory=dict
    )
    device_update_subscriptions: set[CALLBACK_TYPE] = field(default_factory=set)
    static_info_update_subscriptions: set[Callable[[list[EntityInfo]], None]] = field(
        default_factory=set
    )
    loaded_platforms: set[Platform] = field(default_factory=set)
    platform_load_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    _storage_contents: StoreData | None = None
    _pending_storage: Callable[[], StoreData] | None = None
    assist_pipeline_update_callbacks: list[CALLBACK_TYPE] = field(default_factory=list)
    assist_pipeline_state: bool = False
    entity_info_callbacks: dict[
        type[EntityInfo], list[Callable[[list[EntityInfo]], None]]
    ] = field(default_factory=dict)
    entity_info_key_updated_callbacks: dict[
        tuple[type[EntityInfo], int], list[Callable[[EntityInfo], None]]
    ] = field(default_factory=dict)
    original_options: dict[str, Any] = field(default_factory=dict)

    @property
    def name(self) -> str:
        """Return the name of the device."""
        device_info = self.device_info
        return (device_info and device_info.name) or self.title

    @property
    def friendly_name(self) -> str:
        """Return the friendly name of the device."""
        device_info = self.device_info
        return (device_info and device_info.friendly_name) or self.name.title().replace(
            "_", " "
        )

    @callback
    def async_register_static_info_callback(
        self,
        entity_info_type: type[EntityInfo],
        callback_: Callable[[list[EntityInfo]], None],
    ) -> CALLBACK_TYPE:
        """Register to receive callbacks when static info changes for an EntityInfo type."""
        callbacks = self.entity_info_callbacks.setdefault(entity_info_type, [])
        callbacks.append(callback_)
        return partial(
            self._async_unsubscribe_register_static_info, callbacks, callback_
        )

    @callback
    def _async_unsubscribe_register_static_info(
        self,
        callbacks: list[Callable[[list[EntityInfo]], None]],
        callback_: Callable[[list[EntityInfo]], None],
    ) -> None:
        """Unsubscribe to when static info is registered."""
        callbacks.remove(callback_)

    @callback
    def async_register_key_static_info_updated_callback(
        self,
        static_info: EntityInfo,
        callback_: Callable[[EntityInfo], None],
    ) -> CALLBACK_TYPE:
        """Register to receive callbacks when static info is updated for a specific key."""
        callback_key = (type(static_info), static_info.key)
        callbacks = self.entity_info_key_updated_callbacks.setdefault(callback_key, [])
        callbacks.append(callback_)
        return partial(
            self._async_unsubscribe_static_key_info_updated, callbacks, callback_
        )

    @callback
    def _async_unsubscribe_static_key_info_updated(
        self,
        callbacks: list[Callable[[EntityInfo], None]],
        callback_: Callable[[EntityInfo], None],
    ) -> None:
        """Unsubscribe to when static info is updated ."""
        callbacks.remove(callback_)

    @callback
    def async_set_assist_pipeline_state(self, state: bool) -> None:
        """Set the assist pipeline state."""
        self.assist_pipeline_state = state
        for update_callback in self.assist_pipeline_update_callbacks:
            update_callback()

    @callback
    def async_subscribe_assist_pipeline_update(
        self, update_callback: CALLBACK_TYPE
    ) -> CALLBACK_TYPE:
        """Subscribe to assist pipeline updates."""
        self.assist_pipeline_update_callbacks.append(update_callback)
        return partial(self._async_unsubscribe_assist_pipeline_update, update_callback)

    @callback
    def _async_unsubscribe_assist_pipeline_update(
        self, update_callback: CALLBACK_TYPE
    ) -> None:
        """Unsubscribe to assist pipeline updates."""
        self.assist_pipeline_update_callbacks.remove(update_callback)

    @callback
    def async_remove_entities(
        self, hass: HomeAssistant, static_infos: Iterable[EntityInfo], mac: str
    ) -> None:
        """Schedule the removal of an entity."""
        # Remove from entity registry first so the entity is fully removed
        ent_reg = er.async_get(hass)
        for info in static_infos:
            if entry := ent_reg.async_get_entity_id(
                INFO_TYPE_TO_PLATFORM[type(info)], DOMAIN, build_unique_id(mac, info)
            ):
                ent_reg.async_remove(entry)

    @callback
    def async_update_entity_infos(self, static_infos: Iterable[EntityInfo]) -> None:
        """Call static info updated callbacks."""
        callbacks = self.entity_info_key_updated_callbacks
        for static_info in static_infos:
            for callback_ in callbacks.get((type(static_info), static_info.key), ()):
                callback_(static_info)

    async def _ensure_platforms_loaded(
        self,
        hass: HomeAssistant,
        entry: ESPHomeConfigEntry,
        platforms: set[Platform],
    ) -> None:
        async with self.platform_load_lock:
            if needed := platforms - self.loaded_platforms:
                await hass.config_entries.async_forward_entry_setups(entry, needed)
            self.loaded_platforms |= needed

    async def async_update_static_infos(
        self,
        hass: HomeAssistant,
        entry: ESPHomeConfigEntry,
        infos: list[EntityInfo],
        mac: str,
    ) -> None:
        """Distribute an update of static infos to all platforms."""
        # First, load all platforms
        needed_platforms = set()
        if async_get_dashboard(hass):
            needed_platforms.add(Platform.UPDATE)

        if self.device_info and self.device_info.voice_assistant_feature_flags_compat(
            self.api_version
        ):
            needed_platforms.add(Platform.BINARY_SENSOR)
            needed_platforms.add(Platform.SELECT)

        ent_reg = er.async_get(hass)
        registry_get_entity = ent_reg.async_get_entity_id
        for info in infos:
            platform = INFO_TYPE_TO_PLATFORM[type(info)]
            needed_platforms.add(platform)
            # If the unique id is in the old format, migrate it
            # except if they downgraded and upgraded, there might be a duplicate
            # so we want to keep the one that was already there.
            if (
                (old_unique_id := info.unique_id)
                and (old_entry := registry_get_entity(platform, DOMAIN, old_unique_id))
                and (new_unique_id := build_unique_id(mac, info)) != old_unique_id
                and not registry_get_entity(platform, DOMAIN, new_unique_id)
            ):
                ent_reg.async_update_entity(old_entry, new_unique_id=new_unique_id)

        await self._ensure_platforms_loaded(hass, entry, needed_platforms)

        # Make a dict of the EntityInfo by type and send
        # them to the listeners for each specific EntityInfo type
        infos_by_type: dict[type[EntityInfo], list[EntityInfo]] = {}
        for info in infos:
            info_type = type(info)
            if info_type not in infos_by_type:
                infos_by_type[info_type] = []
            infos_by_type[info_type].append(info)

        callbacks_by_type = self.entity_info_callbacks
        for type_, entity_infos in infos_by_type.items():
            if callbacks_ := callbacks_by_type.get(type_):
                for callback_ in callbacks_:
                    callback_(entity_infos)

        # Finally update static info subscriptions
        for callback_ in self.static_info_update_subscriptions:
            callback_(infos)

    @callback
    def async_subscribe_device_updated(self, callback_: CALLBACK_TYPE) -> CALLBACK_TYPE:
        """Subscribe to state updates."""
        self.device_update_subscriptions.add(callback_)
        return partial(self._async_unsubscribe_device_update, callback_)

    @callback
    def _async_unsubscribe_device_update(self, callback_: CALLBACK_TYPE) -> None:
        """Unsubscribe to device updates."""
        self.device_update_subscriptions.remove(callback_)

    @callback
    def async_subscribe_static_info_updated(
        self, callback_: Callable[[list[EntityInfo]], None]
    ) -> CALLBACK_TYPE:
        """Subscribe to static info updates."""
        self.static_info_update_subscriptions.add(callback_)
        return partial(self._async_unsubscribe_static_info_updated, callback_)

    @callback
    def _async_unsubscribe_static_info_updated(
        self, callback_: Callable[[list[EntityInfo]], None]
    ) -> None:
        """Unsubscribe to static info updates."""
        self.static_info_update_subscriptions.remove(callback_)

    @callback
    def async_subscribe_state_update(
        self,
        state_type: type[EntityState],
        state_key: int,
        entity_callback: CALLBACK_TYPE,
    ) -> CALLBACK_TYPE:
        """Subscribe to state updates."""
        subscription_key = (state_type, state_key)
        self.state_subscriptions[subscription_key] = entity_callback
        return partial(self._async_unsubscribe_state_update, subscription_key)

    @callback
    def _async_unsubscribe_state_update(
        self, subscription_key: tuple[type[EntityState], int]
    ) -> None:
        """Unsubscribe to state updates."""
        self.state_subscriptions.pop(subscription_key)

    @callback
    def async_update_state(self, state: EntityState) -> None:
        """Distribute an update of state information to the target."""
        key = state.key
        state_type = type(state)
        stale_state = self.stale_state
        current_state_by_type = self.state[state_type]
        current_state = current_state_by_type.get(key, _SENTINEL)
        subscription_key = (state_type, key)
        if (
            current_state == state
            and subscription_key not in stale_state
            and state_type not in (CameraState, Event)
            and not (
                state_type is SensorState
                and (platform_info := self.info.get(SensorInfo))
                and (entity_info := platform_info.get(state.key))
                and (cast(SensorInfo, entity_info)).force_update
            )
        ):
            return
        stale_state.discard(subscription_key)
        current_state_by_type[key] = state
        if subscription := self.state_subscriptions.get(subscription_key):
            try:
                subscription()
            except Exception:
                # If we allow this exception to raise it will
                # make it all the way to data_received in aioesphomeapi
                # which will cause the connection to be closed.
                _LOGGER.exception("Error while calling subscription")

    @callback
    def async_update_device_state(self) -> None:
        """Distribute an update of a core device state like availability."""
        for callback_ in self.device_update_subscriptions.copy():
            callback_()

    async def async_load_from_store(self) -> tuple[list[EntityInfo], list[UserService]]:
        """Load the retained data from store and return de-serialized data."""
        if (restored := await self.store.async_load()) is None:
            return [], []
        self._storage_contents = restored.copy()

        self.device_info = DeviceInfo.from_dict(restored.pop("device_info"))
        self.api_version = APIVersion.from_dict(restored.pop("api_version", {}))
        infos: list[EntityInfo] = []
        for comp_type, restored_infos in restored.items():
            if TYPE_CHECKING:
                restored_infos = cast(list[dict[str, Any]], restored_infos)
            if comp_type not in COMPONENT_TYPE_TO_INFO:
                continue
            for info in restored_infos:
                cls = COMPONENT_TYPE_TO_INFO[comp_type]
                infos.append(cls.from_dict(info))
        services = [
            UserService.from_dict(service) for service in restored.pop("services", [])
        ]
        return infos, services

    def async_save_to_store(self) -> None:
        """Generate dynamic data to store and save it to the filesystem."""
        if TYPE_CHECKING:
            assert self.device_info is not None
        store_data: StoreData = {
            "device_info": self.device_info.to_dict(),
            "services": [],
            "api_version": self.api_version.to_dict(),
        }
        for info_type, infos in self.info.items():
            comp_type = INFO_TO_COMPONENT_TYPE[info_type]
            store_data[comp_type] = [info.to_dict() for info in infos.values()]  # type: ignore[literal-required]

        store_data["services"] = [
            service.to_dict() for service in self.services.values()
        ]
        if store_data == self._storage_contents:
            return

        def _memorized_storage() -> StoreData:
            self._pending_storage = None
            self._storage_contents = store_data
            return store_data

        self._pending_storage = _memorized_storage
        self.store.async_delay_save(_memorized_storage, SAVE_DELAY)

    async def async_cleanup(self) -> None:
        """Cleanup the entry data when disconnected or unloading."""
        if self._pending_storage:
            # Ensure we save the data if we are unloading before the
            # save delay has passed.
            await self.store.async_save(self._pending_storage())

    async def async_update_listener(
        self, hass: HomeAssistant, entry: ESPHomeConfigEntry
    ) -> None:
        """Handle options update."""
        if self.original_options == entry.options:
            return
        hass.async_create_task(hass.config_entries.async_reload(entry.entry_id))

    @callback
    def async_on_disconnect(self) -> None:
        """Call when the entry has been disconnected.

        Safe to call multiple times.
        """
        self.available = False
        if self.bluetooth_device:
            self.bluetooth_device.available = False
        # Make a copy since calling the disconnect callbacks
        # may also try to discard/remove themselves.
        for disconnect_cb in self.disconnect_callbacks.copy():
            disconnect_cb()
        # Make sure to clear the set to give up the reference
        # to it and make sure all the callbacks can be GC'd.
        self.disconnect_callbacks.clear()
        self.disconnect_callbacks = set()

    @callback
    def async_on_connect(
        self, device_info: DeviceInfo, api_version: APIVersion
    ) -> None:
        """Call when the entry has been connected."""
        self.available = True
        if self.bluetooth_device:
            self.bluetooth_device.available = True

        self.device_info = device_info
        self.api_version = api_version
        # Reset expected disconnect flag on successful reconnect
        # as it will be flipped to False on unexpected disconnect.
        #
        # We use this to determine if a deep sleep device should
        # be marked as unavailable or not.
        self.expected_disconnect = True
