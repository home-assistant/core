"""Data storage helper for ZHA."""
# pylint: disable=unused-import
from collections import OrderedDict
import logging
from typing import MutableMapping, cast

import attr

from homeassistant.core import callback
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.loader import bind_hass

from .typing import ZhaDeviceType, ZhaGroupType

_LOGGER = logging.getLogger(__name__)

DATA_REGISTRY = "zha_storage"

STORAGE_KEY = "zha.storage"
STORAGE_VERSION = 1
SAVE_DELAY = 10


@attr.s(slots=True, frozen=True)
class ZhaDeviceEntry:
    """Zha Device storage Entry."""

    name = attr.ib(type=str, default=None)
    ieee = attr.ib(type=str, default=None)
    last_seen = attr.ib(type=float, default=None)


@attr.s(slots=True, frozen=True)
class ZhaGroupEntry:
    """Zha Group storage Entry."""

    name = attr.ib(type=str, default=None)
    group_id = attr.ib(type=int, default=None)
    entity_domain = attr.ib(type=float, default=None)


class ZhaStorage:
    """Class to hold a registry of zha devices."""

    def __init__(self, hass: HomeAssistantType) -> None:
        """Initialize the zha device storage."""
        self.hass: HomeAssistantType = hass
        self.devices: MutableMapping[str, ZhaDeviceEntry] = {}
        self.groups: MutableMapping[str, ZhaGroupEntry] = {}
        self._store = hass.helpers.storage.Store(STORAGE_VERSION, STORAGE_KEY)

    @callback
    def async_create_device(self, device: ZhaDeviceType) -> ZhaDeviceEntry:
        """Create a new ZhaDeviceEntry."""
        device_entry: ZhaDeviceEntry = ZhaDeviceEntry(
            name=device.name, ieee=str(device.ieee), last_seen=device.last_seen
        )
        self.devices[device_entry.ieee] = device_entry

        return self.async_update_device(device)

    @callback
    def async_create_group(self, group: ZhaGroupType) -> ZhaGroupEntry:
        """Create a new ZhaGroupEntry."""
        group_entry: ZhaGroupEntry = ZhaGroupEntry(
            name=group.name,
            group_id=str(group.group_id),
            entity_domain=group.entity_domain,
        )
        self.groups[str(group.group_id)] = group_entry
        return self.async_update_group(group)

    @callback
    def async_get_or_create_device(self, device: ZhaDeviceType) -> ZhaDeviceEntry:
        """Create a new ZhaDeviceEntry."""
        ieee_str: str = str(device.ieee)
        if ieee_str in self.devices:
            return self.devices[ieee_str]
        return self.async_create_device(device)

    @callback
    def async_get_or_create_group(self, group: ZhaGroupType) -> ZhaGroupEntry:
        """Create a new ZhaGroupEntry."""
        group_id: str = str(group.group_id)
        if group_id in self.groups:
            return self.groups[group_id]
        return self.async_create_group(group)

    @callback
    def async_create_or_update_device(self, device: ZhaDeviceType) -> ZhaDeviceEntry:
        """Create or update a ZhaDeviceEntry."""
        if str(device.ieee) in self.devices:
            return self.async_update_device(device)
        return self.async_create_device(device)

    @callback
    def async_create_or_update_group(self, group: ZhaGroupType) -> ZhaGroupEntry:
        """Create or update a ZhaGroupEntry."""
        if str(group.group_id) in self.groups:
            return self.async_update_group(group)
        return self.async_create_group(group)

    @callback
    def async_delete_device(self, device: ZhaDeviceType) -> None:
        """Delete ZhaDeviceEntry."""
        ieee_str: str = str(device.ieee)
        if ieee_str in self.devices:
            del self.devices[ieee_str]
            self.async_schedule_save()

    @callback
    def async_delete_group(self, group: ZhaGroupType) -> None:
        """Delete ZhaGroupEntry."""
        group_id: str = str(group.group_id)
        if group_id in self.groups:
            del self.groups[group_id]
            self.async_schedule_save()

    @callback
    def async_update_device(self, device: ZhaDeviceType) -> ZhaDeviceEntry:
        """Update name of ZhaDeviceEntry."""
        ieee_str: str = str(device.ieee)
        old = self.devices[ieee_str]

        changes = {}
        changes["last_seen"] = device.last_seen

        new = self.devices[ieee_str] = attr.evolve(old, **changes)
        self.async_schedule_save()
        return new

    @callback
    def async_update_group(self, group: ZhaGroupType) -> ZhaGroupEntry:
        """Update name of ZhaGroupEntry."""
        group_id: str = str(group.group_id)
        old = self.groups[group_id]

        changes = {}
        changes["entity_domain"] = group.entity_domain

        new = self.groups[group_id] = attr.evolve(old, **changes)
        self.async_schedule_save()
        return new

    async def async_load(self) -> None:
        """Load the registry of zha device entries."""
        data = await self._store.async_load()

        devices: "OrderedDict[str, ZhaDeviceEntry]" = OrderedDict()
        groups: "OrderedDict[str, ZhaGroupEntry]" = OrderedDict()

        if data is not None:
            for device in data["devices"]:
                devices[device["ieee"]] = ZhaDeviceEntry(
                    name=device["name"],
                    ieee=device["ieee"],
                    last_seen=device["last_seen"] if "last_seen" in device else None,
                )

            if "groups" in data:
                for group in data["groups"]:
                    groups[group["group_id"]] = ZhaGroupEntry(
                        name=group["name"],
                        group_id=group["group_id"],
                        entity_domain=group["entity_domain"]
                        if "entity_domain" in group
                        else None,
                    )

        self.devices = devices
        self.groups = groups

    @callback
    def async_schedule_save(self) -> None:
        """Schedule saving the registry of zha devices."""
        self._store.async_delay_save(self._data_to_save, SAVE_DELAY)

    async def async_save(self) -> None:
        """Save the registry of zha devices."""
        await self._store.async_save(self._data_to_save())

    @callback
    def _data_to_save(self) -> dict:
        """Return data for the registry of zha devices to store in a file."""
        data = {}

        data["devices"] = [
            {"name": entry.name, "ieee": entry.ieee, "last_seen": entry.last_seen}
            for entry in self.devices.values()
        ]

        data["groups"] = [
            {
                "name": entry.name,
                "group_id": entry.group_id,
                "entity_domain": entry.entity_domain,
            }
            for entry in self.groups.values()
        ]
        return data


@bind_hass
async def async_get_registry(hass: HomeAssistantType) -> ZhaStorage:
    """Return zha device storage instance."""
    task = hass.data.get(DATA_REGISTRY)

    if task is None:

        async def _load_reg() -> ZhaStorage:
            registry = ZhaStorage(hass)
            await registry.async_load()
            return registry

        task = hass.data[DATA_REGISTRY] = hass.async_create_task(_load_reg())

    return cast(ZhaStorage, await task)
