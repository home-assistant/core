"""device_manager."""
from __future__ import annotations

from abc import ABCMeta
import asyncio
from functools import lru_cache
from typing import Optional

from .const import PUSH
from .controller.device import BaseDevice
from .controller.system import SystemAllMixin
from .controller.toggle import ToggleXMix
from .enums import Namespace
from .http_device import HttpDeviceInfo
from .socket_server import SocketServerProtocol

_ABILITY_MATRIX = {
    Namespace.CONTROL_TOGGLEX.value: ToggleXMix,
    Namespace.SYSTEM_ALL.value: SystemAllMixin,
}


class RefossDeviceListener(metaclass=ABCMeta):
    """refoss device listener."""

    def update_device(self, device: BaseDevice):
        """Update device info."""

    def add_device(self, device: BaseDevice):
        """Device Added."""

    def remove_device(self, device_id: str):
        """Device removed."""


class RefossDeviceManager:
    """RefossDeviceManager."""

    def __init__(self, socket_server: SocketServerProtocol) -> None:
        """Initialize."""
        self.base_device_map: dict[str, BaseDevice] = {}
        self.socket_server = socket_server
        self.device_listeners = set()
        self.loop = asyncio.get_event_loop()
        self.tasks=[]
        self.socket_server.register_message_received(self.message_received)

    async def async_start_broadcast_msg(self):
        """Start broadcast."""
        task = asyncio.create_task(self.socket_server.broadcast_msg())
        task.done()
        self.tasks.append(task)

    def message_received(self, data: dict):
        """Received a message from the server."""
        self.handle_broadcast_msg(data)
        self.handle_state_msg(data)

    def handle_broadcast_msg(self, data: dict):
        """Processing broadcast reply messages."""
        if "channels" in data and "uuid" in data:
            device = HttpDeviceInfo.from_dict(data)
            if device is None:
                return
            old_device: BaseDevice = self.base_device_map.get(device.uuid)
            if old_device is not None:
                if old_device.inner_ip == device.inner_ip:
                    return

            asyncio.run_coroutine_threadsafe(
                self.async_update_device(device), loop=self.loop
            )

    def handle_state_msg(self, data: dict):
        """Processing status reporting messages."""
        if "payload" in data and "header" in data:
            if data is not None:
                header = data.get("header", {})
                namespace = header.get("namespace")
                uuid = header.get("uuid")
                method = header.get("method")
                payload = data.get("payload")
                if namespace is None or uuid is None or payload is None:
                    return

                if method != PUSH:
                    return

                baseDevice: BaseDevice = self.base_device_map.get(uuid)

                if baseDevice is None:
                    return

                asyncio.run_coroutine_threadsafe(
                    baseDevice.async_handle_push_notification(
                        namespace=namespace, data=payload, uuid=uuid
                    ),
                    loop=self.loop,
                )

    async def async_update_device(self, device_info: HttpDeviceInfo):
        """async_update_device."""
        device = await self.async_build_base_device(device_info)
        if device is not None:
            for listener in self.device_listeners:
                listener.add_device(device)

    async def async_build_base_device(
        self, device_info: HttpDeviceInfo
    ) -> Optional[BaseDevice]:
        """Build base device."""
        device = None
        res = await device_info.async_execute_cmd(
            device_uuid=device_info.uuid,
            method="GET",
            namespace=Namespace.SYSTEM_ABILITY,
            payload={},
        )
        if res is None:
            return device

        abilities = res.get("payload", {}).get("ability", None)

        if abilities is not None:
            device = build_device_from_abilities(
                http_device_info=device_info, device_abilities=abilities
            )

        if device is not None:
            self.base_device_map[device_info.uuid] = device

        return device

    # async def update_device_caches(self):
    #     device_list =await self.socket_server.async_socket_find_devices()
    #     for device in device_list:
    #         await self.async_build_base_device(device)

    def add_device_listener(self, listener: RefossDeviceListener):
        """Add a device listener."""
        self.device_listeners.add(listener)

    def remove_device_listener(self, listener: RefossDeviceListener):
        """Remove device listener."""
        self.device_listeners.remove(listener)


_dynamic_types: dict[str, type] = {}


@lru_cache(maxsize=512)
def _lookup_cached_type(
    device_type: str, hardware_version: str, firmware_version: str
) -> Optional[type]:
    """Lookup."""
    lookup_string = _caclulate_device_type_name(
        device_type, hardware_version, firmware_version
    ).strip(":")
    return _dynamic_types.get(lookup_string)


def build_device_from_abilities(
    http_device_info: HttpDeviceInfo, device_abilities: dict
) -> BaseDevice:
    """build_device_from_abilities."""
    cached_type = _lookup_cached_type(
        http_device_info.device_type,
        http_device_info.hdware_version,
        http_device_info.fmware_version,
    )
    if cached_type is None:
        device_type_name = _caclulate_device_type_name(
            http_device_info.device_type,
            http_device_info.hdware_version,
            http_device_info.fmware_version,
        )

        base_class = BaseDevice

        cached_type = _build_cached_type(
            type_string=device_type_name,
            device_abilities=device_abilities,
            base_class=base_class,
        )
        _dynamic_types[device_type_name] = cached_type

    component = cached_type(device=http_device_info)
    return component


def _caclulate_device_type_name(
    device_type: str, hardware_version: str, firmware_version: str
) -> str:
    """_caclulate_device_type_name."""
    return f"{device_type}:{hardware_version}:{firmware_version}"


def _build_cached_type(
    type_string: str, device_abilities: dict, base_class: type
) -> type:
    """_build_cached_type."""
    mixin_classes = set()

    for key, _value in device_abilities.items():
        clsx = None
        cls = _ABILITY_MATRIX.get(key)

        # Check if for this ability the device exposes the X version
        x_key = f"{key}X"
        x_version_ability = device_abilities.get(x_key)
        if x_version_ability is not None:
            clsx = _ABILITY_MATRIX.get(x_key)

        # Now, if we have both the clsx and the cls, prefer the clsx, otherwise go for the cls
        if clsx is not None:
            mixin_classes.add(clsx)
        elif cls is not None:
            mixin_classes.add(cls)

    classes_list = list(mixin_classes)
    classes_list.append(base_class)
    m = type(type_string, tuple(classes_list), {"_abilities_spec": device_abilities})
    return m
