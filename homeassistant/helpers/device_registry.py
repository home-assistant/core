"""Provide a way to connect entities belonging to one device."""
import logging
import uuid

from collections import OrderedDict

import attr

from homeassistant.core import callback
from homeassistant.loader import bind_hass

_LOGGER = logging.getLogger(__name__)
_UNDEF = object()

DATA_REGISTRY = 'device_registry'

STORAGE_KEY = 'core.device_registry'
STORAGE_VERSION = 1
SAVE_DELAY = 10

CONNECTION_NETWORK_MAC = 'mac'
CONNECTION_ZIGBEE = 'zigbee'


@attr.s(slots=True, frozen=True)
class DeviceEntry:
    """Device Registry Entry."""

    config_entries = attr.ib(type=set, converter=set)
    connections = attr.ib(type=set, converter=set)
    identifiers = attr.ib(type=set, converter=set)
    manufacturer = attr.ib(type=str)
    model = attr.ib(type=str)
    name = attr.ib(type=str, default=None)
    sw_version = attr.ib(type=str, default=None)
    hub_device_id = attr.ib(type=str, default=None)
    id = attr.ib(type=str, default=attr.Factory(lambda: uuid.uuid4().hex))


class DeviceRegistry:
    """Class to hold a registry of devices."""

    def __init__(self, hass):
        """Initialize the device registry."""
        self.hass = hass
        self.devices = None
        self._store = hass.helpers.storage.Store(STORAGE_VERSION, STORAGE_KEY)

    @callback
    def async_get_device(self, identifiers: set, connections: set):
        """Check if device is registered."""
        for device in self.devices.values():
            if any(iden in device.identifiers for iden in identifiers) or \
                    any(conn in device.connections for conn in connections):
                return device
        return None

    @callback
    def async_get_or_create(self, *, config_entry_id, connections, identifiers,
                            manufacturer, model, name=None, sw_version=None,
                            via_hub=None):
        """Get device. Create if it doesn't exist."""
        if not identifiers and not connections:
            return None

        device = self.async_get_device(identifiers, connections)

        if via_hub is not None:
            hub_device = self.async_get_device({via_hub}, set())
            hub_device_id = hub_device.id if hub_device else None
        else:
            hub_device_id = None

        if device is not None:
            return self._async_update_device(
                device.id, config_entry_id=config_entry_id,
                hub_device_id=hub_device_id
            )

        device = DeviceEntry(
            config_entries={config_entry_id},
            connections=connections,
            identifiers=identifiers,
            manufacturer=manufacturer,
            model=model,
            name=name,
            sw_version=sw_version,
            hub_device_id=hub_device_id
        )
        self.devices[device.id] = device

        self.async_schedule_save()

        return device

    @callback
    def _async_update_device(self, device_id, *, config_entry_id=_UNDEF,
                             remove_config_entry_id=_UNDEF,
                             hub_device_id=_UNDEF):
        """Update device attributes."""
        old = self.devices[device_id]

        changes = {}

        config_entries = old.config_entries

        if (config_entry_id is not _UNDEF and
                config_entry_id not in old.config_entries):
            config_entries = old.config_entries | {config_entry_id}

        if (remove_config_entry_id is not _UNDEF and
                remove_config_entry_id in config_entries):
            config_entries = set(config_entries)
            config_entries.remove(remove_config_entry_id)

        if config_entries is not old.config_entries:
            changes['config_entries'] = config_entries

        if (hub_device_id is not _UNDEF and
                hub_device_id != old.hub_device_id):
            changes['hub_device_id'] = hub_device_id

        if not changes:
            return old

        new = self.devices[device_id] = attr.evolve(old, **changes)
        self.async_schedule_save()
        return new

    async def async_load(self):
        """Load the device registry."""
        data = await self._store.async_load()

        devices = OrderedDict()

        if data is not None:
            for device in data['devices']:
                devices[device['id']] = DeviceEntry(
                    config_entries=set(device['config_entries']),
                    connections={tuple(conn) for conn
                                 in device['connections']},
                    identifiers={tuple(iden) for iden
                                 in device['identifiers']},
                    manufacturer=device['manufacturer'],
                    model=device['model'],
                    name=device['name'],
                    sw_version=device['sw_version'],
                    id=device['id'],
                    # Introduced in 0.79
                    hub_device_id=device.get('hub_device_id'),
                )

        self.devices = devices

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
                'config_entries': list(entry.config_entries),
                'connections': list(entry.connections),
                'identifiers': list(entry.identifiers),
                'manufacturer': entry.manufacturer,
                'model': entry.model,
                'name': entry.name,
                'sw_version': entry.sw_version,
                'id': entry.id,
                'hub_device_id': entry.hub_device_id,
            } for entry in self.devices.values()
        ]

        return data

    @callback
    def async_clear_config_entry(self, config_entry_id):
        """Clear config entry from registry entries."""
        for dev_id, device in self.devices.items():
            if config_entry_id in device.config_entries:
                self._async_update_device(
                    dev_id, remove_config_entry_id=config_entry_id)


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
