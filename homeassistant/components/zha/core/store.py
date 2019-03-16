"""Data storage helper for ZHA."""
import logging
from collections import OrderedDict
# pylint: disable=W0611
from typing import MutableMapping  # noqa: F401
from typing import cast

import attr

from homeassistant.core import callback
from homeassistant.loader import bind_hass
from homeassistant.helpers.typing import HomeAssistantType

_LOGGER = logging.getLogger(__name__)

DATA_REGISTRY = 'zha_storage'

STORAGE_KEY = 'zha.storage'
STORAGE_VERSION = 1
SAVE_DELAY = 10


@attr.s(slots=True, frozen=True)
class ZhaDeviceEntry:
    """Zha Device storage Entry."""

    name = attr.ib(type=str, default=None)
    ieee = attr.ib(type=str, default=None)
    power_source = attr.ib(type=int, default=None)
    manufacturer_code = attr.ib(type=int, default=None)
    last_seen = attr.ib(type=float, default=None)


class ZhaDeviceStorage:
    """Class to hold a registry of zha devices."""

    def __init__(self, hass: HomeAssistantType) -> None:
        """Initialize the zha device storage."""
        self.hass = hass
        self.devices = {}  # type: MutableMapping[str, ZhaDeviceEntry]
        self._store = hass.helpers.storage.Store(STORAGE_VERSION, STORAGE_KEY)

    @callback
    def async_create(self, device) -> ZhaDeviceEntry:
        """Create a new ZhaDeviceEntry."""
        device_entry = ZhaDeviceEntry(
            name=device.name,
            ieee=str(device.ieee),
            power_source=device.power_source,
            manufacturer_code=device.manufacturer_code,
            last_seen=device.last_seen

        )
        self.devices[device_entry.ieee] = device_entry

        return self.async_update(device)

    @callback
    def async_get_or_create(self, device) -> ZhaDeviceEntry:
        """Create a new ZhaDeviceEntry."""
        ieee_str = str(device.ieee)
        if ieee_str in self.devices:
            return self.devices[ieee_str]
        return self.async_create(device)

    @callback
    def async_create_or_update(self, device) -> ZhaDeviceEntry:
        """Create or update a ZhaDeviceEntry."""
        if str(device.ieee) in self.devices:
            return self.async_update(device)
        return self.async_create(device)

    @callback
    def async_delete(self, device) -> None:
        """Delete ZhaDeviceEntry."""
        ieee_str = str(device.ieee)
        if ieee_str in self.devices:
            del self.devices[ieee_str]
            self.async_schedule_save()

    @callback
    def async_update(self, device) -> ZhaDeviceEntry:
        """Update name of ZhaDeviceEntry."""
        ieee_str = str(device.ieee)
        old = self.devices[ieee_str]

        changes = {}

        if device.power_source != old.power_source:
            changes['power_source'] = device.power_source

        if device.manufacturer_code != old.manufacturer_code:
            changes['manufacturer_code'] = device.manufacturer_code

        changes['last_seen'] = device.last_seen

        new = self.devices[ieee_str] = attr.evolve(old, **changes)
        self.async_schedule_save()
        return new

    async def async_load(self) -> None:
        """Load the registry of zha device entries."""
        data = await self._store.async_load()

        devices = OrderedDict()  # type: OrderedDict[str, ZhaDeviceEntry]

        if data is not None:
            for device in data['devices']:
                devices[device['ieee']] = ZhaDeviceEntry(
                    name=device['name'],
                    ieee=device['ieee'],
                    power_source=device['power_source'],
                    manufacturer_code=device['manufacturer_code'],
                    last_seen=device['last_seen'] if 'last_seen' in device
                    else None
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

        data['devices'] = [
            {
                'name': entry.name,
                'ieee': entry.ieee,
                'power_source': entry.power_source,
                'manufacturer_code': entry.manufacturer_code,
                'last_seen': entry.last_seen
            } for entry in self.devices.values()
        ]

        return data


@bind_hass
async def async_get_registry(hass: HomeAssistantType) -> ZhaDeviceStorage:
    """Return zha device storage instance."""
    task = hass.data.get(DATA_REGISTRY)

    if task is None:
        async def _load_reg() -> ZhaDeviceStorage:
            registry = ZhaDeviceStorage(hass)
            await registry.async_load()
            return registry

        task = hass.data[DATA_REGISTRY] = hass.async_create_task(_load_reg())

    return cast(ZhaDeviceStorage, await task)
