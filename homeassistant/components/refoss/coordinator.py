"""Coordinators for the Refoss integration."""
from typing import TypeVar, Dict, Optional, TypeGuard
import async_timeout
from collections.abc import Iterable
import asyncio
from asyncio import AbstractEventLoop
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.core import HomeAssistant

from refoss_ha.socket_util import pushStateDataList
from refoss_ha.http_device import HttpDeviceInfo
from refoss_ha.controller.device import BaseDevice
from refoss_ha.socket_util import SocketUtil
from refoss_ha.enums import Namespace
from refoss_ha.controller.toggle import ToggleXMix
from refoss_ha.controller.system import SystemAllMixin
from refoss_ha.const import LOGGER, PUSH, DOMAIN
from homeassistant.helpers import device_registry as dr

T = TypeVar("T", bound=BaseDevice)


_ABILITY_MATRIX = {
    Namespace.CONTROL_TOGGLEX.value: ToggleXMix,
    Namespace.SYSTEM_ALL.value: SystemAllMixin,
}


class RefossCoordinator(DataUpdateCoordinator):
    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        update_interval: timedelta,
        loop: Optional[AbstractEventLoop] = None,
    ):
        self._entry = config_entry
        self._devices_by_internal_id: Dict[str, BaseDevice] = {}
        self._setup_done = False
        self.socket = SocketUtil()
        self._loop = asyncio.get_event_loop() if loop is None else loop

        super().__init__(
            hass=hass,
            logger=LOGGER,
            name="refoss_coordinator",
            update_interval=update_interval,
            update_method=self._async_fetch_data,
        )

    async def initial_setup(self):
        if self._setup_done:
            raise ValueError("This coordinator was already set up")

        # Listening for socket messages
        self.socket.startReveiveMsg()

        asyncio.create_task(self.HandlePushState())

        devicelist = self.socket.async_socket_find_devices()
        self.async_set_updated_data({device.uuid: device for device in devicelist})

        await self.async_device_discovery(cached_http_device_list=devicelist)

        self._setup_done = True
        LOGGER.info("Initial_setup ok")

    async def _async_fetch_data(self):
        async with async_timeout.timeout(10):
            devices = self.socket.async_socket_find_devices()
            return {device.uuid: device for device in devices}

    def find_devices(self, device_uuids: Optional[Iterable[str]] = None) -> list[T]:
        res = self._devices_by_internal_id.values()

        if device_uuids is not None:
            res = filter(lambda d: TypeGuard[bool](d.uuid in device_uuids), res)

        return list(res)

    async def _async_enroll_new_http_dev(
        self, device_info: HttpDeviceInfo
    ) -> Optional[BaseDevice]:
        device = None
        abilities = None

        try:
            res = await device_info.async_execute_cmd(
                device_uuid=device_info.uuid,
                method="GET",
                namespace=Namespace.SYSTEM_ABILITY,
                payload={},
            )

            abilities = res.get("payload", {}).get("ability")

        except Exception as e:
            LOGGER.warning(
                f"Device %s (%s) is online, but timeout occurred "
                f"when fetching its abilities. Reason: %s",
                str(device_info.dev_name),
                str(device_info.uuid),
                e,
            )
        if abilities is not None:
            device = build_device_from_abilities(
                http_device_info=device_info, device_abilities=abilities
            )

        if device is not None:
            self.enroll_device(device)

        return device

    def enroll_device(self, device: BaseDevice):
        if device.uuid in self._devices_by_internal_id:
            return
        else:
            self._devices_by_internal_id[device.uuid] = device

    def lookup_base_by_uuid(self, device_uuid: str) -> BaseDevice:
        res = [
            d for d in self._devices_by_internal_id.values() if d.uuid == device_uuid
        ]
        if len(res) > 1:
            LOGGER.warning(f"Multiple devices found for device_uuid {device_uuid}")
            return None
        if len(res) == 1:
            return res[0]
        return None

    async def async_device_discovery(
        self,
        device_uuid: Optional[str] = None,
        cached_http_device_list: list[HttpDeviceInfo] = None,
    ) -> list[BaseDevice]:
        if cached_http_device_list is None:
            http_devices = self.socket.async_socket_find_devices()
        else:
            http_devices = cached_http_device_list

        if device_uuid is not None:
            http_devices = [d for d in http_devices if d.uuid == device_uuid]

        res = []
        for device in http_devices:
            if self.lookup_base_by_uuid(device.uuid) is not None:
                exists_device = self.lookup_base_by_uuid(device.uuid)
                if exists_device.inner_ip == device.inner_ip:
                    continue
                device_registry = dr.async_get(self.hass)
                device_entry = device_registry.async_get_device(
                    identifiers={(DOMAIN, device.uuid)}
                )
                if device_entry is not None:
                    device_registry.async_remove_device(device_entry.id)
                    self._devices_by_internal_id.pop(device.uuid)

            dev = await self._async_enroll_new_http_dev(device)

            if dev is not None:
                res.append(dev)

        return res

    async def HandlePushState(self):
        while True:
            if len(pushStateDataList) == 0:
                await asyncio.sleep(3)
                continue

            data = pushStateDataList.pop(0)
            if data is not None:
                try:
                    header = data.get("header", {})
                    namespace = header.get("namespace")
                    uuid = header.get("uuid")
                    method = header.get("method")
                    payload = data.get("payload")
                    if namespace is None or uuid is None or payload is None:
                        continue

                    if method != PUSH:
                        continue

                    baseDevice: BaseDevice = self.lookup_base_by_uuid(uuid)

                    if baseDevice is None:
                        continue

                    asyncio.run_coroutine_threadsafe(
                        baseDevice.async_handle_push_notification(
                            namespace=namespace, data=payload, uuid=uuid
                        ),
                        loop=self._loop,
                    )
                except Exception as e:
                    LOGGER.warning("HandlePushState, %s", e)


_dynamic_types: Dict[str, type] = {}


def build_device_from_abilities(
    http_device_info: HttpDeviceInfo, device_abilities: dict
) -> BaseDevice:
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
    return f"{device_type}:{hardware_version}:{firmware_version}"


def _lookup_cached_type(
    device_type: str, hardware_version: str, firmware_version: str
) -> Optional[type]:
    lookup_string = _caclulate_device_type_name(
        device_type, hardware_version, firmware_version
    ).strip(":")
    return _dynamic_types.get(lookup_string)


def _build_cached_type(
    type_string: str, device_abilities: dict, base_class: type
) -> type:
    mixin_classes = set()

    for key, val in device_abilities.items():
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
