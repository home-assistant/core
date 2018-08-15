"""Provide a way to connect entities belonging to one device.
"""

import logging
import uuid

import attr

from homeassistant.core import callback
from homeassistant.loader import bind_hass

_LOGGER = logging.getLogger(__name__)

STORAGE_KEY = 'core.device_registry'
STORAGE_VERSION = 1
STORAGE_DELAY = 1

DATA_REGISTRY = 'device_registry'


@attr.s(slots=True, frozen=True)
class DeviceEntry:
    """Device Registry Entry."""

    identifiers = attr.ib(type=list)
    manufacturer = attr.ib(type=str)
    model = attr.ib(type=str)
    connection = attr.ib(type=list)
    sw_version = attr.ib(type=str, default=None)
    id = attr.ib(type=str, default=attr.Factory(lambda: uuid.uuid4().hex))


class DeviceRegistry:
    """Class to hold a registry of devices."""

    def __init__(self, hass):
        """Initialize the device registry."""
        self.hass = hass
        self.devices = None
        self._load_task = None
        self._sched_save = None
        self._store = hass.helpers.storage.Store(STORAGE_VERSION, STORAGE_KEY)

    @callback
    def async_get_device(self, identifiers: str, connection: tuple):
        """Check if device is registered."""
        for device in self.devices:
            if device.identifiers == identifiers or \
                    device.connection == connection:
                return device
        return None

    async def async_get_or_create(self, identifiers, manufacturer, model,
                            connection, *, sw_version=None):
        """Get device. Create if it doesn't exist"""
        device = self.async_get_device(identifiers, connection)
        if device is None:
            device = DeviceEntry(
                identifiers=identifiers,
                manufacturer=manufacturer,
                model=model,
                connection=connection,
                sw_version=sw_version
            )
            self.devices.append(device)
            await self.async_save()
        return device

    async def async_ensure_loaded(self):
        """Load the registry from disk."""
        if self.devices is not None:
            return
        devices = await self._store.async_load()
        if devices is None:
            self.devices = []
            return
        self.devices = [DeviceEntry(**device) for device in devices['devices']]

    async def async_save(self):
        """Save the device registry to a file."""
        data = {
            'devices': [attr.asdict(device) for device in self.devices]
        }
        await self._store.async_save(data, delay=STORAGE_DELAY)


@bind_hass
async def async_get_registry(hass) -> DeviceRegistry:
    """Return device registry instance."""
    registry = hass.data.get(DATA_REGISTRY)

    if registry is None:
        registry = hass.data[DATA_REGISTRY] = DeviceRegistry(hass)

    await registry.async_ensure_loaded()
    return registry
