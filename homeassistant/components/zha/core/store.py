"""Data storage helper for ZHA."""
from __future__ import annotations

from collections import OrderedDict
import datetime
import time
from typing import MutableMapping, cast

import attr

from homeassistant.core import callback
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.loader import bind_hass

from .typing import ZhaDeviceType

DATA_REGISTRY = "zha_storage"

STORAGE_KEY = "zha.storage"
STORAGE_VERSION = 1
SAVE_DELAY = 10
TOMBSTONE_LIFETIME = datetime.timedelta(days=60).total_seconds()


@attr.s(slots=True, frozen=True)
class ZhaDeviceEntry:
    """Zha Device storage Entry."""

    name: str | None = attr.ib(default=None)
    ieee: str | None = attr.ib(default=None)
    last_seen: float | None = attr.ib(default=None)


class ZhaStorage:
    """Class to hold a registry of zha devices."""

    def __init__(self, hass: HomeAssistantType) -> None:
        """Initialize the zha device storage."""
        self.hass: HomeAssistantType = hass
        self.devices: MutableMapping[str, ZhaDeviceEntry] = {}
        self._store = hass.helpers.storage.Store(STORAGE_VERSION, STORAGE_KEY)

    @callback
    def async_create_device(self, device: ZhaDeviceType) -> ZhaDeviceEntry:
        """Create a new ZhaDeviceEntry."""
        device_entry: ZhaDeviceEntry = ZhaDeviceEntry(
            name=device.name, ieee=str(device.ieee), last_seen=device.last_seen
        )
        self.devices[device_entry.ieee] = device_entry
        self.async_schedule_save()
        return device_entry

    @callback
    def async_get_or_create_device(self, device: ZhaDeviceType) -> ZhaDeviceEntry:
        """Create a new ZhaDeviceEntry."""
        ieee_str: str = str(device.ieee)
        if ieee_str in self.devices:
            return self.devices[ieee_str]
        return self.async_create_device(device)

    @callback
    def async_create_or_update_device(self, device: ZhaDeviceType) -> ZhaDeviceEntry:
        """Create or update a ZhaDeviceEntry."""
        if str(device.ieee) in self.devices:
            return self.async_update_device(device)
        return self.async_create_device(device)

    @callback
    def async_delete_device(self, device: ZhaDeviceType) -> None:
        """Delete ZhaDeviceEntry."""
        ieee_str: str = str(device.ieee)
        if ieee_str in self.devices:
            del self.devices[ieee_str]
            self.async_schedule_save()

    @callback
    def async_update_device(self, device: ZhaDeviceType) -> ZhaDeviceEntry:
        """Update name of ZhaDeviceEntry."""
        ieee_str: str = str(device.ieee)
        old = self.devices[ieee_str]

        if old is not None and device.last_seen is None:
            return

        changes = {}
        changes["last_seen"] = device.last_seen

        new = self.devices[ieee_str] = attr.evolve(old, **changes)
        self.async_schedule_save()
        return new

    async def async_load(self) -> None:
        """Load the registry of zha device entries."""
        data = await self._store.async_load()

        devices: OrderedDict[str, ZhaDeviceEntry] = OrderedDict()

        if data is not None:
            for device in data["devices"]:
                devices[device["ieee"]] = ZhaDeviceEntry(
                    name=device["name"],
                    ieee=device["ieee"],
                    last_seen=device.get("last_seen"),
                )

        self.devices = devices

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
            if entry.last_seen and (time.time() - entry.last_seen) < TOMBSTONE_LIFETIME
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
