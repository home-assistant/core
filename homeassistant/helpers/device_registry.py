"""Provide a way to connect entities belonging to one device."""
import logging
import uuid

import attr

from homeassistant.core import callback
from homeassistant.loader import bind_hass

_LOGGER = logging.getLogger(__name__)

DATA_REGISTRY = 'device_registry'

STORAGE_KEY = 'core.device_registry'
STORAGE_VERSION = 1
SAVE_DELAY = 10

CONNECTION_NETWORK_MAC = 'mac'
CONNECTION_ZIGBEE = 'zigbee'


@attr.s(slots=True, frozen=True)
class DeviceEntry:
    """Device Registry Entry."""

    connection = attr.ib(type=list)
    identifiers = attr.ib(type=list)
    manufacturer = attr.ib(type=str)
    model = attr.ib(type=str)
    name = attr.ib(type=str, default=None)
    sw_version = attr.ib(type=str, default=None)
    id = attr.ib(type=str, default=attr.Factory(lambda: uuid.uuid4().hex))


class DeviceRegistry:
    """Class to hold a registry of devices."""

    def __init__(self, hass):
        """Initialize the device registry."""
        self.hass = hass
        self.devices = None
        self._store = hass.helpers.storage.Store(STORAGE_VERSION, STORAGE_KEY)

    @callback
    def async_get_device(self, identifiers: str, connections: tuple):
        """Check if device is registered."""
        for device in self.devices:
            if any(iden in device.identifiers for iden in identifiers) or \
                    any(conn in device.connection for conn in connections):
                return device
        return None

    @callback
    def async_get_or_create(self, *, connection, identifiers, manufacturer,
                            model, name=None, sw_version=None):
        """Get device. Create if it doesn't exist."""
        device = self.async_get_device(identifiers, connection)

        if device is not None:
            return device

        device = DeviceEntry(
            connection=connection,
            identifiers=identifiers,
            manufacturer=manufacturer,
            model=model,
            name=name,
            sw_version=sw_version
        )

        self.devices.append(device)
        self.async_schedule_save()

        return device

    async def async_load(self):
        """Load the device registry."""
        devices = await self._store.async_load()

        if devices is None:
            self.devices = []
            return

        self.devices = [DeviceEntry(**device) for device in devices['devices']]

    @callback
    def async_schedule_save(self):
        """Schedule saving the device registry."""
        self._store.async_delay_save(self._data_to_save, SAVE_DELAY)

    @callback
    def _data_to_save(self):
        """Return data of device registry to store in a file."""
        data = {}

        data['devices'] = [
            {
                'id': entry.id,
                'connection': entry.connection,
                'identifiers': entry.identifiers,
                'manufacturer': entry.manufacturer,
                'model': entry.model,
                'name': entry.name,
                'sw_version': entry.sw_version,
            } for entry in self.devices
        ]

        return data


@bind_hass
async def async_get_registry(hass) -> DeviceRegistry:
    """Return device registry instance."""
    task = hass.data.get(DATA_REGISTRY)

    if task is None:
        async def _load_reg():
            registry = DeviceRegistry(hass)
            await registry.async_load()
            return registry

        task = hass.data[DATA_REGISTRY] = hass.async_create_task(_load_reg())

    return await task
