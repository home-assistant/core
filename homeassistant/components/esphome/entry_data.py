"""Runtime entry data for ESPHome stored in hass.data."""
import asyncio
from typing import Any, Callable, Dict, List, Optional, Tuple

from aioesphomeapi import (
    COMPONENT_TYPE_TO_INFO, DeviceInfo, EntityInfo, EntityState, UserService)
import attr

from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import HomeAssistantType

DATA_KEY = 'esphome'
DISPATCHER_UPDATE_ENTITY = 'esphome_{entry_id}_update_{component_key}_{key}'
DISPATCHER_REMOVE_ENTITY = 'esphome_{entry_id}_remove_{component_key}_{key}'
DISPATCHER_ON_LIST = 'esphome_{entry_id}_on_list'
DISPATCHER_ON_DEVICE_UPDATE = 'esphome_{entry_id}_on_device_update'
DISPATCHER_ON_STATE = 'esphome_{entry_id}_on_state'


@attr.s
class RuntimeEntryData:
    """Store runtime data for esphome config entries."""

    entry_id = attr.ib(type=str)
    client = attr.ib(type='APIClient')
    store = attr.ib(type=Store)
    reconnect_task = attr.ib(type=Optional[asyncio.Task], default=None)
    state = attr.ib(type=Dict[str, Dict[str, Any]], factory=dict)
    info = attr.ib(type=Dict[str, Dict[str, Any]], factory=dict)
    services = attr.ib(type=Dict[int, 'UserService'], factory=dict)
    available = attr.ib(type=bool, default=False)
    device_info = attr.ib(type=DeviceInfo, default=None)
    cleanup_callbacks = attr.ib(type=List[Callable[[], None]], factory=list)
    disconnect_callbacks = attr.ib(type=List[Callable[[], None]], factory=list)

    def async_update_entity(self, hass: HomeAssistantType, component_key: str,
                            key: int) -> None:
        """Schedule the update of an entity."""
        signal = DISPATCHER_UPDATE_ENTITY.format(
            entry_id=self.entry_id, component_key=component_key, key=key)
        async_dispatcher_send(hass, signal)

    def async_remove_entity(self, hass: HomeAssistantType, component_key: str,
                            key: int) -> None:
        """Schedule the removal of an entity."""
        signal = DISPATCHER_REMOVE_ENTITY.format(
            entry_id=self.entry_id, component_key=component_key, key=key)
        async_dispatcher_send(hass, signal)

    def async_update_static_infos(self, hass: HomeAssistantType,
                                  infos: List[EntityInfo]) -> None:
        """Distribute an update of static infos to all platforms."""
        signal = DISPATCHER_ON_LIST.format(entry_id=self.entry_id)
        async_dispatcher_send(hass, signal, infos)

    def async_update_state(self, hass: HomeAssistantType,
                           state: EntityState) -> None:
        """Distribute an update of state information to all platforms."""
        signal = DISPATCHER_ON_STATE.format(entry_id=self.entry_id)
        async_dispatcher_send(hass, signal, state)

    def async_update_device_state(self, hass: HomeAssistantType) -> None:
        """Distribute an update of a core device state like availability."""
        signal = DISPATCHER_ON_DEVICE_UPDATE.format(entry_id=self.entry_id)
        async_dispatcher_send(hass, signal)

    async def async_load_from_store(self) -> Tuple[List[EntityInfo],
                                                   List[UserService]]:
        """Load the retained data from store and return de-serialized data."""
        restored = await self.store.async_load()
        if restored is None:
            return [], []

        self.device_info = _attr_obj_from_dict(DeviceInfo,
                                               **restored.pop('device_info'))
        infos = []
        for comp_type, restored_infos in restored.items():
            if comp_type not in COMPONENT_TYPE_TO_INFO:
                continue
            for info in restored_infos:
                cls = COMPONENT_TYPE_TO_INFO[comp_type]
                infos.append(_attr_obj_from_dict(cls, **info))
        services = []
        for service in restored.get('services', []):
            services.append(UserService.from_dict(service))
        return infos, services

    async def async_save_to_store(self) -> None:
        """Generate dynamic data to store and save it to the filesystem."""
        store_data = {
            'device_info': attr.asdict(self.device_info),
            'services': []
        }

        for comp_type, infos in self.info.items():
            store_data[comp_type] = [attr.asdict(info)
                                     for info in infos.values()]
        for service in self.services.values():
            store_data['services'].append(service.to_dict())

        await self.store.async_save(store_data)


def _attr_obj_from_dict(cls, **kwargs):
    return cls(**{key: kwargs[key] for key in attr.fields_dict(cls)
                  if key in kwargs})
