"""Provide a way to connect entities belonging to one device."""
from collections import OrderedDict
import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Tuple, Union

import attr

from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import Event, callback
import homeassistant.util.uuid as uuid_util

from .debounce import Debouncer
from .singleton import singleton
from .typing import HomeAssistantType

if TYPE_CHECKING:
    from . import entity_registry

# mypy: allow-untyped-calls, allow-untyped-defs, no-check-untyped-defs

_LOGGER = logging.getLogger(__name__)
_UNDEF = object()

DATA_REGISTRY = "device_registry"
EVENT_DEVICE_REGISTRY_UPDATED = "device_registry_updated"
STORAGE_KEY = "core.device_registry"
STORAGE_VERSION = 1
SAVE_DELAY = 10
CLEANUP_DELAY = 10

CONNECTION_NETWORK_MAC = "mac"
CONNECTION_UPNP = "upnp"
CONNECTION_ZIGBEE = "zigbee"

IDX_CONNECTIONS = "connections"
IDX_IDENTIFIERS = "identifiers"
REGISTERED_DEVICE = "registered"
DELETED_DEVICE = "deleted"

DISABLED_INTEGRATION = "integration"
DISABLED_USER = "user"


@attr.s(slots=True, frozen=True)
class DeletedDeviceEntry:
    """Deleted Device Registry Entry."""

    config_entries: Set[str] = attr.ib()
    connections: Set[Tuple[str, str]] = attr.ib()
    identifiers: Set[Tuple[str, str]] = attr.ib()
    id: str = attr.ib()

    def to_device_entry(self, config_entry_id, connections, identifiers):
        """Create DeviceEntry from DeletedDeviceEntry."""
        return DeviceEntry(
            config_entries={config_entry_id},
            connections=self.connections & connections,
            identifiers=self.identifiers & identifiers,
            id=self.id,
            is_new=True,
        )


@attr.s(slots=True, frozen=True)
class DeviceEntry:
    """Device Registry Entry."""

    config_entries: Set[str] = attr.ib(converter=set, factory=set)
    connections: Set[Tuple[str, str]] = attr.ib(converter=set, factory=set)
    identifiers: Set[Tuple[str, str]] = attr.ib(converter=set, factory=set)
    manufacturer: str = attr.ib(default=None)
    model: str = attr.ib(default=None)
    name: str = attr.ib(default=None)
    sw_version: str = attr.ib(default=None)
    via_device_id: str = attr.ib(default=None)
    area_id: str = attr.ib(default=None)
    name_by_user: str = attr.ib(default=None)
    entry_type: str = attr.ib(default=None)
    id: str = attr.ib(factory=uuid_util.random_uuid_hex)
    # This value is not stored, just used to keep track of events to fire.
    is_new: bool = attr.ib(default=False)
    disabled_by: Optional[str] = attr.ib(
        default=None,
        validator=attr.validators.in_(
            (
                DISABLED_INTEGRATION,
                DISABLED_USER,
                None,
            )
        ),
    )

    @property
    def disabled(self) -> bool:
        """Return if entry is disabled."""
        return self.disabled_by is not None


def format_mac(mac: str) -> str:
    """Format the mac address string for entry into dev reg."""
    to_test = mac

    if len(to_test) == 17 and to_test.count(":") == 5:
        return to_test.lower()

    if len(to_test) == 17 and to_test.count("-") == 5:
        to_test = to_test.replace("-", "")
    elif len(to_test) == 14 and to_test.count(".") == 2:
        to_test = to_test.replace(".", "")

    if len(to_test) == 12:
        # no : included
        return ":".join(to_test.lower()[i : i + 2] for i in range(0, 12, 2))

    # Not sure how formatted, return original
    return mac


class DeviceRegistry:
    """Class to hold a registry of devices."""

    devices: Dict[str, DeviceEntry]
    deleted_devices: Dict[str, DeletedDeviceEntry]
    _devices_index: Dict[str, Dict[str, Dict[str, str]]]

    def __init__(self, hass: HomeAssistantType) -> None:
        """Initialize the device registry."""
        self.hass = hass
        self._store = hass.helpers.storage.Store(STORAGE_VERSION, STORAGE_KEY)
        self._clear_index()

    @callback
    def async_get(self, device_id: str) -> Optional[DeviceEntry]:
        """Get device."""
        return self.devices.get(device_id)

    @callback
    def async_get_device(
        self, identifiers: set, connections: set
    ) -> Optional[DeviceEntry]:
        """Check if device is registered."""
        device_id = self._async_get_device_id_from_index(
            REGISTERED_DEVICE, identifiers, connections
        )
        if device_id is None:
            return None
        return self.devices[device_id]

    def _async_get_deleted_device(
        self, identifiers: set, connections: set
    ) -> Optional[DeletedDeviceEntry]:
        """Check if device is deleted."""
        device_id = self._async_get_device_id_from_index(
            DELETED_DEVICE, identifiers, connections
        )
        if device_id is None:
            return None
        return self.deleted_devices[device_id]

    def _async_get_device_id_from_index(
        self, index: str, identifiers: set, connections: set
    ) -> Optional[str]:
        """Check if device has previously been registered."""
        devices_index = self._devices_index[index]
        for identifier in identifiers:
            if identifier in devices_index[IDX_IDENTIFIERS]:
                return devices_index[IDX_IDENTIFIERS][identifier]
        if not connections:
            return None
        for connection in _normalize_connections(connections):
            if connection in devices_index[IDX_CONNECTIONS]:
                return devices_index[IDX_CONNECTIONS][connection]
        return None

    def _add_device(self, device: Union[DeviceEntry, DeletedDeviceEntry]) -> None:
        """Add a device and index it."""
        if isinstance(device, DeletedDeviceEntry):
            devices_index = self._devices_index[DELETED_DEVICE]
            self.deleted_devices[device.id] = device
        else:
            devices_index = self._devices_index[REGISTERED_DEVICE]
            self.devices[device.id] = device

        _add_device_to_index(devices_index, device)

    def _remove_device(self, device: Union[DeviceEntry, DeletedDeviceEntry]) -> None:
        """Remove a device and remove it from the index."""
        if isinstance(device, DeletedDeviceEntry):
            devices_index = self._devices_index[DELETED_DEVICE]
            self.deleted_devices.pop(device.id)
        else:
            devices_index = self._devices_index[REGISTERED_DEVICE]
            self.devices.pop(device.id)

        _remove_device_from_index(devices_index, device)

    def _update_device(self, old_device: DeviceEntry, new_device: DeviceEntry) -> None:
        """Update a device and the index."""
        self.devices[new_device.id] = new_device

        devices_index = self._devices_index[REGISTERED_DEVICE]
        _remove_device_from_index(devices_index, old_device)
        _add_device_to_index(devices_index, new_device)

    def _clear_index(self):
        """Clear the index."""
        self._devices_index = {
            REGISTERED_DEVICE: {IDX_IDENTIFIERS: {}, IDX_CONNECTIONS: {}},
            DELETED_DEVICE: {IDX_IDENTIFIERS: {}, IDX_CONNECTIONS: {}},
        }

    def _rebuild_index(self):
        """Create the index after loading devices."""
        self._clear_index()
        for device in self.devices.values():
            _add_device_to_index(self._devices_index[REGISTERED_DEVICE], device)
        for device in self.deleted_devices.values():
            _add_device_to_index(self._devices_index[DELETED_DEVICE], device)

    @callback
    def async_get_or_create(
        self,
        *,
        config_entry_id,
        connections=None,
        identifiers=None,
        manufacturer=_UNDEF,
        model=_UNDEF,
        name=_UNDEF,
        default_manufacturer=_UNDEF,
        default_model=_UNDEF,
        default_name=_UNDEF,
        sw_version=_UNDEF,
        entry_type=_UNDEF,
        via_device=None,
        # To disable a device if it gets created
        disabled_by=_UNDEF,
    ):
        """Get device. Create if it doesn't exist."""
        if not identifiers and not connections:
            return None

        if identifiers is None:
            identifiers = set()

        if connections is None:
            connections = set()
        else:
            connections = _normalize_connections(connections)

        device = self.async_get_device(identifiers, connections)

        if device is None:
            deleted_device = self._async_get_deleted_device(identifiers, connections)
            if deleted_device is None:
                device = DeviceEntry(is_new=True)
            else:
                self._remove_device(deleted_device)
                device = deleted_device.to_device_entry(
                    config_entry_id, connections, identifiers
                )
            self._add_device(device)

        if default_manufacturer is not _UNDEF and device.manufacturer is None:
            manufacturer = default_manufacturer

        if default_model is not _UNDEF and device.model is None:
            model = default_model

        if default_name is not _UNDEF and device.name is None:
            name = default_name

        if via_device is not None:
            via = self.async_get_device({via_device}, set())
            via_device_id = via.id if via else _UNDEF
        else:
            via_device_id = _UNDEF

        return self._async_update_device(
            device.id,
            add_config_entry_id=config_entry_id,
            via_device_id=via_device_id,
            merge_connections=connections or _UNDEF,
            merge_identifiers=identifiers or _UNDEF,
            manufacturer=manufacturer,
            model=model,
            name=name,
            sw_version=sw_version,
            entry_type=entry_type,
            disabled_by=disabled_by,
        )

    @callback
    def async_update_device(
        self,
        device_id,
        *,
        area_id=_UNDEF,
        manufacturer=_UNDEF,
        model=_UNDEF,
        name=_UNDEF,
        name_by_user=_UNDEF,
        new_identifiers=_UNDEF,
        sw_version=_UNDEF,
        via_device_id=_UNDEF,
        remove_config_entry_id=_UNDEF,
        disabled_by=_UNDEF,
    ):
        """Update properties of a device."""
        return self._async_update_device(
            device_id,
            area_id=area_id,
            manufacturer=manufacturer,
            model=model,
            name=name,
            name_by_user=name_by_user,
            new_identifiers=new_identifiers,
            sw_version=sw_version,
            via_device_id=via_device_id,
            remove_config_entry_id=remove_config_entry_id,
            disabled_by=disabled_by,
        )

    @callback
    def _async_update_device(
        self,
        device_id,
        *,
        add_config_entry_id=_UNDEF,
        remove_config_entry_id=_UNDEF,
        merge_connections=_UNDEF,
        merge_identifiers=_UNDEF,
        new_identifiers=_UNDEF,
        manufacturer=_UNDEF,
        model=_UNDEF,
        name=_UNDEF,
        sw_version=_UNDEF,
        entry_type=_UNDEF,
        via_device_id=_UNDEF,
        area_id=_UNDEF,
        name_by_user=_UNDEF,
        disabled_by=_UNDEF,
    ):
        """Update device attributes."""
        old = self.devices[device_id]

        changes = {}

        config_entries = old.config_entries

        if (
            add_config_entry_id is not _UNDEF
            and add_config_entry_id not in old.config_entries
        ):
            config_entries = old.config_entries | {add_config_entry_id}

        if (
            remove_config_entry_id is not _UNDEF
            and remove_config_entry_id in config_entries
        ):
            if config_entries == {remove_config_entry_id}:
                self.async_remove_device(device_id)
                return

            config_entries = config_entries - {remove_config_entry_id}

        if config_entries != old.config_entries:
            changes["config_entries"] = config_entries

        for attr_name, value in (
            ("connections", merge_connections),
            ("identifiers", merge_identifiers),
        ):
            old_value = getattr(old, attr_name)
            # If not undefined, check if `value` contains new items.
            if value is not _UNDEF and not value.issubset(old_value):
                changes[attr_name] = old_value | value

        if new_identifiers is not _UNDEF:
            changes["identifiers"] = new_identifiers

        for attr_name, value in (
            ("manufacturer", manufacturer),
            ("model", model),
            ("name", name),
            ("sw_version", sw_version),
            ("entry_type", entry_type),
            ("via_device_id", via_device_id),
            ("disabled_by", disabled_by),
        ):
            if value is not _UNDEF and value != getattr(old, attr_name):
                changes[attr_name] = value

        if area_id is not _UNDEF and area_id != old.area_id:
            changes["area_id"] = area_id

        if name_by_user is not _UNDEF and name_by_user != old.name_by_user:
            changes["name_by_user"] = name_by_user

        if old.is_new:
            changes["is_new"] = False

        if not changes:
            return old

        new = attr.evolve(old, **changes)
        self._update_device(old, new)
        self.async_schedule_save()

        self.hass.bus.async_fire(
            EVENT_DEVICE_REGISTRY_UPDATED,
            {
                "action": "create" if "is_new" in changes else "update",
                "device_id": new.id,
            },
        )

        return new

    @callback
    def async_remove_device(self, device_id: str) -> None:
        """Remove a device from the device registry."""
        device = self.devices[device_id]
        self._remove_device(device)
        self._add_device(
            DeletedDeviceEntry(
                config_entries=device.config_entries,
                connections=device.connections,
                identifiers=device.identifiers,
                id=device.id,
            )
        )
        self.hass.bus.async_fire(
            EVENT_DEVICE_REGISTRY_UPDATED, {"action": "remove", "device_id": device_id}
        )
        self.async_schedule_save()

    async def async_load(self):
        """Load the device registry."""
        async_setup_cleanup(self.hass, self)

        data = await self._store.async_load()

        devices = OrderedDict()
        deleted_devices = OrderedDict()

        if data is not None:
            for device in data["devices"]:
                devices[device["id"]] = DeviceEntry(
                    config_entries=set(device["config_entries"]),
                    connections={tuple(conn) for conn in device["connections"]},
                    identifiers={tuple(iden) for iden in device["identifiers"]},
                    manufacturer=device["manufacturer"],
                    model=device["model"],
                    name=device["name"],
                    sw_version=device["sw_version"],
                    # Introduced in 0.110
                    entry_type=device.get("entry_type"),
                    id=device["id"],
                    # Introduced in 0.79
                    # renamed in 0.95
                    via_device_id=(
                        device.get("via_device_id") or device.get("hub_device_id")
                    ),
                    # Introduced in 0.87
                    area_id=device.get("area_id"),
                    name_by_user=device.get("name_by_user"),
                    # Introduced in 0.119
                    disabled_by=device.get("disabled_by"),
                )
            # Introduced in 0.111
            for device in data.get("deleted_devices", []):
                deleted_devices[device["id"]] = DeletedDeviceEntry(
                    config_entries=set(device["config_entries"]),
                    connections={tuple(conn) for conn in device["connections"]},
                    identifiers={tuple(iden) for iden in device["identifiers"]},
                    id=device["id"],
                )

        self.devices = devices
        self.deleted_devices = deleted_devices
        self._rebuild_index()

    @callback
    def async_schedule_save(self) -> None:
        """Schedule saving the device registry."""
        self._store.async_delay_save(self._data_to_save, SAVE_DELAY)

    @callback
    def _data_to_save(self) -> Dict[str, List[Dict[str, Any]]]:
        """Return data of device registry to store in a file."""
        data = {}

        data["devices"] = [
            {
                "config_entries": list(entry.config_entries),
                "connections": list(entry.connections),
                "identifiers": list(entry.identifiers),
                "manufacturer": entry.manufacturer,
                "model": entry.model,
                "name": entry.name,
                "sw_version": entry.sw_version,
                "entry_type": entry.entry_type,
                "id": entry.id,
                "via_device_id": entry.via_device_id,
                "area_id": entry.area_id,
                "name_by_user": entry.name_by_user,
                "disabled_by": entry.disabled_by,
            }
            for entry in self.devices.values()
        ]
        data["deleted_devices"] = [
            {
                "config_entries": list(entry.config_entries),
                "connections": list(entry.connections),
                "identifiers": list(entry.identifiers),
                "id": entry.id,
            }
            for entry in self.deleted_devices.values()
        ]

        return data

    @callback
    def async_clear_config_entry(self, config_entry_id: str) -> None:
        """Clear config entry from registry entries."""
        for device in list(self.devices.values()):
            self._async_update_device(device.id, remove_config_entry_id=config_entry_id)
        for deleted_device in list(self.deleted_devices.values()):
            config_entries = deleted_device.config_entries
            if config_entry_id not in config_entries:
                continue
            if config_entries == {config_entry_id}:
                # Permanently remove the device from the device registry.
                self._remove_device(deleted_device)
            else:
                config_entries = config_entries - {config_entry_id}
                # No need to reindex here since we currently
                # do not have a lookup by config entry
                self.deleted_devices[deleted_device.id] = attr.evolve(
                    deleted_device, config_entries=config_entries
                )
            self.async_schedule_save()

    @callback
    def async_clear_area_id(self, area_id: str) -> None:
        """Clear area id from registry entries."""
        for dev_id, device in self.devices.items():
            if area_id == device.area_id:
                self._async_update_device(dev_id, area_id=None)


@singleton(DATA_REGISTRY)
async def async_get_registry(hass: HomeAssistantType) -> DeviceRegistry:
    """Create entity registry."""
    reg = DeviceRegistry(hass)
    await reg.async_load()
    return reg


@callback
def async_entries_for_area(registry: DeviceRegistry, area_id: str) -> List[DeviceEntry]:
    """Return entries that match an area."""
    return [device for device in registry.devices.values() if device.area_id == area_id]


@callback
def async_entries_for_config_entry(
    registry: DeviceRegistry, config_entry_id: str
) -> List[DeviceEntry]:
    """Return entries that match a config entry."""
    return [
        device
        for device in registry.devices.values()
        if config_entry_id in device.config_entries
    ]


@callback
def async_cleanup(
    hass: HomeAssistantType,
    dev_reg: DeviceRegistry,
    ent_reg: "entity_registry.EntityRegistry",
) -> None:
    """Clean up device registry."""
    # Find all devices that are referenced by a config_entry.
    config_entry_ids = {entry.entry_id for entry in hass.config_entries.async_entries()}
    references_config_entries = {
        device.id
        for device in dev_reg.devices.values()
        for config_entry_id in device.config_entries
        if config_entry_id in config_entry_ids
    }

    # Find all devices that are referenced in the entity registry.
    references_entities = {entry.device_id for entry in ent_reg.entities.values()}

    orphan = set(dev_reg.devices) - references_entities - references_config_entries

    for dev_id in orphan:
        dev_reg.async_remove_device(dev_id)

    # Find all referenced config entries that no longer exist
    # This shouldn't happen but have not been able to track down the bug :(
    for device in list(dev_reg.devices.values()):
        for config_entry_id in device.config_entries:
            if config_entry_id not in config_entry_ids:
                dev_reg.async_update_device(
                    device.id, remove_config_entry_id=config_entry_id
                )


@callback
def async_setup_cleanup(hass: HomeAssistantType, dev_reg: DeviceRegistry) -> None:
    """Clean up device registry when entities removed."""
    from . import entity_registry  # pylint: disable=import-outside-toplevel

    async def cleanup():
        """Cleanup."""
        ent_reg = await entity_registry.async_get_registry(hass)
        async_cleanup(hass, dev_reg, ent_reg)

    debounced_cleanup = Debouncer(
        hass, _LOGGER, cooldown=CLEANUP_DELAY, immediate=False, function=cleanup
    )

    async def entity_registry_changed(event: Event) -> None:
        """Handle entity updated or removed."""
        if (
            event.data["action"] == "update"
            and "device_id" not in event.data["changes"]
        ) or event.data["action"] == "create":
            return

        await debounced_cleanup.async_call()

    if hass.is_running:
        hass.bus.async_listen(
            entity_registry.EVENT_ENTITY_REGISTRY_UPDATED, entity_registry_changed
        )
        return

    async def startup_clean(event: Event) -> None:
        """Clean up on startup."""
        hass.bus.async_listen(
            entity_registry.EVENT_ENTITY_REGISTRY_UPDATED, entity_registry_changed
        )
        await debounced_cleanup.async_call()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, startup_clean)


def _normalize_connections(connections: set) -> set:
    """Normalize connections to ensure we can match mac addresses."""
    return {
        (key, format_mac(value)) if key == CONNECTION_NETWORK_MAC else (key, value)
        for key, value in connections
    }


def _add_device_to_index(
    devices_index: dict, device: Union[DeviceEntry, DeletedDeviceEntry]
) -> None:
    """Add a device to the index."""
    for identifier in device.identifiers:
        devices_index[IDX_IDENTIFIERS][identifier] = device.id
    for connection in device.connections:
        devices_index[IDX_CONNECTIONS][connection] = device.id


def _remove_device_from_index(
    devices_index: dict, device: Union[DeviceEntry, DeletedDeviceEntry]
) -> None:
    """Remove a device from the index."""
    for identifier in device.identifiers:
        if identifier in devices_index[IDX_IDENTIFIERS]:
            del devices_index[IDX_IDENTIFIERS][identifier]
    for connection in device.connections:
        if connection in devices_index[IDX_CONNECTIONS]:
            del devices_index[IDX_CONNECTIONS][connection]
