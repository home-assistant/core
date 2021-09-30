"""Provide a way to connect entities belonging to one device."""
from __future__ import annotations

from collections import OrderedDict
import logging
import time
from typing import TYPE_CHECKING, Any, NamedTuple, cast

import attr

from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import RequiredParameterMissing
from homeassistant.loader import bind_hass
import homeassistant.util.uuid as uuid_util

from .debounce import Debouncer
from .typing import UNDEFINED, UndefinedType

# mypy: disallow_any_generics

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

    from . import entity_registry

_LOGGER = logging.getLogger(__name__)

DATA_REGISTRY = "device_registry"
EVENT_DEVICE_REGISTRY_UPDATED = "device_registry_updated"
STORAGE_KEY = "core.device_registry"
STORAGE_VERSION = 1
SAVE_DELAY = 10
CLEANUP_DELAY = 10

CONNECTION_NETWORK_MAC = "mac"
CONNECTION_UPNP = "upnp"
CONNECTION_ZIGBEE = "zigbee"

DISABLED_CONFIG_ENTRY = "config_entry"
DISABLED_INTEGRATION = "integration"
DISABLED_USER = "user"

ORPHANED_DEVICE_KEEP_SECONDS = 86400 * 30


class _DeviceIndex(NamedTuple):
    identifiers: dict[tuple[str, str], str]
    connections: dict[tuple[str, str], str]


@attr.s(slots=True, frozen=True)
class DeviceEntry:
    """Device Registry Entry."""

    config_entries: set[str] = attr.ib(converter=set, factory=set)
    connections: set[tuple[str, str]] = attr.ib(converter=set, factory=set)
    identifiers: set[tuple[str, str]] = attr.ib(converter=set, factory=set)
    manufacturer: str | None = attr.ib(default=None)
    model: str | None = attr.ib(default=None)
    name: str | None = attr.ib(default=None)
    sw_version: str | None = attr.ib(default=None)
    via_device_id: str | None = attr.ib(default=None)
    area_id: str | None = attr.ib(default=None)
    name_by_user: str | None = attr.ib(default=None)
    entry_type: str | None = attr.ib(default=None)
    id: str = attr.ib(factory=uuid_util.random_uuid_hex)
    # This value is not stored, just used to keep track of events to fire.
    is_new: bool = attr.ib(default=False)
    disabled_by: str | None = attr.ib(
        default=None,
        validator=attr.validators.in_(
            (
                DISABLED_CONFIG_ENTRY,
                DISABLED_INTEGRATION,
                DISABLED_USER,
                None,
            )
        ),
    )
    suggested_area: str | None = attr.ib(default=None)

    @property
    def disabled(self) -> bool:
        """Return if entry is disabled."""
        return self.disabled_by is not None


@attr.s(slots=True, frozen=True)
class DeletedDeviceEntry:
    """Deleted Device Registry Entry."""

    config_entries: set[str] = attr.ib()
    connections: set[tuple[str, str]] = attr.ib()
    identifiers: set[tuple[str, str]] = attr.ib()
    id: str = attr.ib()
    orphaned_timestamp: float | None = attr.ib()

    def to_device_entry(
        self,
        config_entry_id: str,
        connections: set[tuple[str, str]],
        identifiers: set[tuple[str, str]],
    ) -> DeviceEntry:
        """Create DeviceEntry from DeletedDeviceEntry."""
        return DeviceEntry(
            # type ignores: likely https://github.com/python/mypy/issues/8625
            config_entries={config_entry_id},  # type: ignore[arg-type]
            connections=self.connections & connections,  # type: ignore[arg-type]
            identifiers=self.identifiers & identifiers,  # type: ignore[arg-type]
            id=self.id,
            is_new=True,
        )


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


def _async_get_device_id_from_index(
    devices_index: _DeviceIndex,
    identifiers: set[tuple[str, str]],
    connections: set[tuple[str, str]] | None,
) -> str | None:
    """Check if device has previously been registered."""
    for identifier in identifiers:
        if identifier in devices_index.identifiers:
            return devices_index.identifiers[identifier]
    if not connections:
        return None
    for connection in _normalize_connections(connections):
        if connection in devices_index.connections:
            return devices_index.connections[connection]
    return None


class DeviceRegistry:
    """Class to hold a registry of devices."""

    devices: dict[str, DeviceEntry]
    deleted_devices: dict[str, DeletedDeviceEntry]
    _registered_index: _DeviceIndex
    _deleted_index: _DeviceIndex

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the device registry."""
        self.hass = hass
        self._store = hass.helpers.storage.Store(STORAGE_VERSION, STORAGE_KEY)
        self._clear_index()

    @callback
    def async_get(self, device_id: str) -> DeviceEntry | None:
        """Get device."""
        return self.devices.get(device_id)

    @callback
    def async_get_device(
        self,
        identifiers: set[tuple[str, str]],
        connections: set[tuple[str, str]] | None = None,
    ) -> DeviceEntry | None:
        """Check if device is registered."""
        device_id = _async_get_device_id_from_index(
            self._registered_index, identifiers, connections
        )
        if device_id is None:
            return None
        return self.devices[device_id]

    def _async_get_deleted_device(
        self,
        identifiers: set[tuple[str, str]],
        connections: set[tuple[str, str]] | None,
    ) -> DeletedDeviceEntry | None:
        """Check if device is deleted."""
        device_id = _async_get_device_id_from_index(
            self._deleted_index, identifiers, connections
        )
        if device_id is None:
            return None
        return self.deleted_devices[device_id]

    def _add_device(self, device: DeviceEntry | DeletedDeviceEntry) -> None:
        """Add a device and index it."""
        if isinstance(device, DeletedDeviceEntry):
            devices_index = self._deleted_index
            self.deleted_devices[device.id] = device
        else:
            devices_index = self._registered_index
            self.devices[device.id] = device

        _add_device_to_index(devices_index, device)

    def _remove_device(self, device: DeviceEntry | DeletedDeviceEntry) -> None:
        """Remove a device and remove it from the index."""
        if isinstance(device, DeletedDeviceEntry):
            devices_index = self._deleted_index
            self.deleted_devices.pop(device.id)
        else:
            devices_index = self._registered_index
            self.devices.pop(device.id)

        _remove_device_from_index(devices_index, device)

    def _update_device(self, old_device: DeviceEntry, new_device: DeviceEntry) -> None:
        """Update a device and the index."""
        self.devices[new_device.id] = new_device

        devices_index = self._registered_index
        _remove_device_from_index(devices_index, old_device)
        _add_device_to_index(devices_index, new_device)

    def _clear_index(self) -> None:
        """Clear the index."""
        self._registered_index = _DeviceIndex(identifiers={}, connections={})
        self._deleted_index = _DeviceIndex(identifiers={}, connections={})

    def _rebuild_index(self) -> None:
        """Create the index after loading devices."""
        self._clear_index()
        for device in self.devices.values():
            _add_device_to_index(self._registered_index, device)
        for deleted_device in self.deleted_devices.values():
            _add_device_to_index(self._deleted_index, deleted_device)

    @callback
    def async_get_or_create(
        self,
        *,
        config_entry_id: str,
        connections: set[tuple[str, str]] | None = None,
        identifiers: set[tuple[str, str]] | None = None,
        manufacturer: str | None | UndefinedType = UNDEFINED,
        model: str | None | UndefinedType = UNDEFINED,
        name: str | None | UndefinedType = UNDEFINED,
        default_manufacturer: str | None | UndefinedType = UNDEFINED,
        default_model: str | None | UndefinedType = UNDEFINED,
        default_name: str | None | UndefinedType = UNDEFINED,
        sw_version: str | None | UndefinedType = UNDEFINED,
        entry_type: str | None | UndefinedType = UNDEFINED,
        via_device: tuple[str, str] | None = None,
        # To disable a device if it gets created
        disabled_by: str | None | UndefinedType = UNDEFINED,
        suggested_area: str | None | UndefinedType = UNDEFINED,
    ) -> DeviceEntry:
        """Get device. Create if it doesn't exist."""
        if not identifiers and not connections:
            raise RequiredParameterMissing(["identifiers", "connections"])

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

        if default_manufacturer is not UNDEFINED and device.manufacturer is None:
            manufacturer = default_manufacturer

        if default_model is not UNDEFINED and device.model is None:
            model = default_model

        if default_name is not UNDEFINED and device.name is None:
            name = default_name

        if via_device is not None:
            via = self.async_get_device({via_device})
            via_device_id: str | UndefinedType = via.id if via else UNDEFINED
        else:
            via_device_id = UNDEFINED

        device = self._async_update_device(
            device.id,
            add_config_entry_id=config_entry_id,
            via_device_id=via_device_id,
            merge_connections=connections or UNDEFINED,
            merge_identifiers=identifiers or UNDEFINED,
            manufacturer=manufacturer,
            model=model,
            name=name,
            sw_version=sw_version,
            entry_type=entry_type,
            disabled_by=disabled_by,
            suggested_area=suggested_area,
        )

        # This is safe because _async_update_device will always return a device
        # in this use case.
        assert device
        return device

    @callback
    def async_update_device(
        self,
        device_id: str,
        *,
        area_id: str | None | UndefinedType = UNDEFINED,
        manufacturer: str | None | UndefinedType = UNDEFINED,
        model: str | None | UndefinedType = UNDEFINED,
        name: str | None | UndefinedType = UNDEFINED,
        name_by_user: str | None | UndefinedType = UNDEFINED,
        new_identifiers: set[tuple[str, str]] | UndefinedType = UNDEFINED,
        sw_version: str | None | UndefinedType = UNDEFINED,
        via_device_id: str | None | UndefinedType = UNDEFINED,
        remove_config_entry_id: str | UndefinedType = UNDEFINED,
        disabled_by: str | None | UndefinedType = UNDEFINED,
        suggested_area: str | None | UndefinedType = UNDEFINED,
    ) -> DeviceEntry | None:
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
            suggested_area=suggested_area,
        )

    @callback
    def _async_update_device(
        self,
        device_id: str,
        *,
        add_config_entry_id: str | UndefinedType = UNDEFINED,
        remove_config_entry_id: str | UndefinedType = UNDEFINED,
        merge_connections: set[tuple[str, str]] | UndefinedType = UNDEFINED,
        merge_identifiers: set[tuple[str, str]] | UndefinedType = UNDEFINED,
        new_identifiers: set[tuple[str, str]] | UndefinedType = UNDEFINED,
        manufacturer: str | None | UndefinedType = UNDEFINED,
        model: str | None | UndefinedType = UNDEFINED,
        name: str | None | UndefinedType = UNDEFINED,
        sw_version: str | None | UndefinedType = UNDEFINED,
        entry_type: str | None | UndefinedType = UNDEFINED,
        via_device_id: str | None | UndefinedType = UNDEFINED,
        area_id: str | None | UndefinedType = UNDEFINED,
        name_by_user: str | None | UndefinedType = UNDEFINED,
        disabled_by: str | None | UndefinedType = UNDEFINED,
        suggested_area: str | None | UndefinedType = UNDEFINED,
    ) -> DeviceEntry | None:
        """Update device attributes."""
        old = self.devices[device_id]

        changes: dict[str, Any] = {}

        config_entries = old.config_entries

        if (
            suggested_area not in (UNDEFINED, None, "")
            and area_id is UNDEFINED
            and old.area_id is None
        ):
            area = self.hass.helpers.area_registry.async_get(
                self.hass
            ).async_get_or_create(suggested_area)
            area_id = area.id

        if (
            add_config_entry_id is not UNDEFINED
            and add_config_entry_id not in old.config_entries
        ):
            config_entries = old.config_entries | {add_config_entry_id}

        if (
            remove_config_entry_id is not UNDEFINED
            and remove_config_entry_id in config_entries
        ):
            if config_entries == {remove_config_entry_id}:
                self.async_remove_device(device_id)
                return None

            config_entries = config_entries - {remove_config_entry_id}

        if config_entries != old.config_entries:
            changes["config_entries"] = config_entries

        for attr_name, setvalue in (
            ("connections", merge_connections),
            ("identifiers", merge_identifiers),
        ):
            old_value = getattr(old, attr_name)
            # If not undefined, check if `value` contains new items.
            if setvalue is not UNDEFINED and not setvalue.issubset(old_value):
                changes[attr_name] = old_value | setvalue

        if new_identifiers is not UNDEFINED:
            changes["identifiers"] = new_identifiers

        for attr_name, value in (
            ("manufacturer", manufacturer),
            ("model", model),
            ("name", name),
            ("sw_version", sw_version),
            ("entry_type", entry_type),
            ("via_device_id", via_device_id),
            ("disabled_by", disabled_by),
            ("suggested_area", suggested_area),
        ):
            if value is not UNDEFINED and value != getattr(old, attr_name):
                changes[attr_name] = value

        if area_id is not UNDEFINED and area_id != old.area_id:
            changes["area_id"] = area_id

        if name_by_user is not UNDEFINED and name_by_user != old.name_by_user:
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
                orphaned_timestamp=None,
            )
        )
        self.hass.bus.async_fire(
            EVENT_DEVICE_REGISTRY_UPDATED, {"action": "remove", "device_id": device_id}
        )
        self.async_schedule_save()

    async def async_load(self) -> None:
        """Load the device registry."""
        async_setup_cleanup(self.hass, self)

        data = await self._store.async_load()

        devices = OrderedDict()
        deleted_devices = OrderedDict()

        if data is not None:
            for device in data["devices"]:
                devices[device["id"]] = DeviceEntry(
                    config_entries=set(device["config_entries"]),
                    # type ignores (if tuple arg was cast): likely https://github.com/python/mypy/issues/8625
                    connections={tuple(conn) for conn in device["connections"]},  # type: ignore[misc]
                    identifiers={tuple(iden) for iden in device["identifiers"]},  # type: ignore[misc]
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
                    # type ignores (if tuple arg was cast): likely https://github.com/python/mypy/issues/8625
                    connections={tuple(conn) for conn in device["connections"]},  # type: ignore[misc]
                    identifiers={tuple(iden) for iden in device["identifiers"]},  # type: ignore[misc]
                    id=device["id"],
                    # Introduced in 2021.2
                    orphaned_timestamp=device.get("orphaned_timestamp"),
                )

        self.devices = devices
        self.deleted_devices = deleted_devices
        self._rebuild_index()

    @callback
    def async_schedule_save(self) -> None:
        """Schedule saving the device registry."""
        self._store.async_delay_save(self._data_to_save, SAVE_DELAY)

    @callback
    def _data_to_save(self) -> dict[str, list[dict[str, Any]]]:
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
                "orphaned_timestamp": entry.orphaned_timestamp,
            }
            for entry in self.deleted_devices.values()
        ]

        return data

    @callback
    def async_clear_config_entry(self, config_entry_id: str) -> None:
        """Clear config entry from registry entries."""
        now_time = time.time()
        for device in list(self.devices.values()):
            self._async_update_device(device.id, remove_config_entry_id=config_entry_id)
        for deleted_device in list(self.deleted_devices.values()):
            config_entries = deleted_device.config_entries
            if config_entry_id not in config_entries:
                continue
            if config_entries == {config_entry_id}:
                # Add a time stamp when the deleted device became orphaned
                self.deleted_devices[deleted_device.id] = attr.evolve(
                    deleted_device, orphaned_timestamp=now_time, config_entries=set()
                )
            else:
                config_entries = config_entries - {config_entry_id}
                # No need to reindex here since we currently
                # do not have a lookup by config entry
                self.deleted_devices[deleted_device.id] = attr.evolve(
                    deleted_device, config_entries=config_entries
                )
            self.async_schedule_save()

    @callback
    def async_purge_expired_orphaned_devices(self) -> None:
        """Purge expired orphaned devices from the registry.

        We need to purge these periodically to avoid the database
        growing without bound.
        """
        now_time = time.time()
        for deleted_device in list(self.deleted_devices.values()):
            if deleted_device.orphaned_timestamp is None:
                continue

            if (
                deleted_device.orphaned_timestamp + ORPHANED_DEVICE_KEEP_SECONDS
                < now_time
            ):
                self._remove_device(deleted_device)

    @callback
    def async_clear_area_id(self, area_id: str) -> None:
        """Clear area id from registry entries."""
        for dev_id, device in self.devices.items():
            if area_id == device.area_id:
                self._async_update_device(dev_id, area_id=None)


@callback
def async_get(hass: HomeAssistant) -> DeviceRegistry:
    """Get device registry."""
    return cast(DeviceRegistry, hass.data[DATA_REGISTRY])


async def async_load(hass: HomeAssistant) -> None:
    """Load device registry."""
    assert DATA_REGISTRY not in hass.data
    hass.data[DATA_REGISTRY] = DeviceRegistry(hass)
    await hass.data[DATA_REGISTRY].async_load()


@bind_hass
async def async_get_registry(hass: HomeAssistant) -> DeviceRegistry:
    """Get device registry.

    This is deprecated and will be removed in the future. Use async_get instead.
    """
    return async_get(hass)


@callback
def async_entries_for_area(registry: DeviceRegistry, area_id: str) -> list[DeviceEntry]:
    """Return entries that match an area."""
    return [device for device in registry.devices.values() if device.area_id == area_id]


@callback
def async_entries_for_config_entry(
    registry: DeviceRegistry, config_entry_id: str
) -> list[DeviceEntry]:
    """Return entries that match a config entry."""
    return [
        device
        for device in registry.devices.values()
        if config_entry_id in device.config_entries
    ]


@callback
def async_config_entry_disabled_by_changed(
    registry: DeviceRegistry, config_entry: ConfigEntry
) -> None:
    """Handle a config entry being disabled or enabled.

    Disable devices in the registry that are associated with a config entry when
    the config entry is disabled, enable devices in the registry that are associated
    with a config entry when the config entry is enabled and the devices are marked
    DISABLED_CONFIG_ENTRY.
    Only disable a device if all associated config entries are disabled.
    """

    devices = async_entries_for_config_entry(registry, config_entry.entry_id)

    if not config_entry.disabled_by:
        for device in devices:
            if device.disabled_by != DISABLED_CONFIG_ENTRY:
                continue
            registry.async_update_device(device.id, disabled_by=None)
        return

    enabled_config_entries = {
        entry.entry_id
        for entry in registry.hass.config_entries.async_entries()
        if not entry.disabled_by
    }

    for device in devices:
        if device.disabled:
            # Device already disabled, do not overwrite
            continue
        if len(device.config_entries) > 1 and device.config_entries.intersection(
            enabled_config_entries
        ):
            continue
        registry.async_update_device(device.id, disabled_by=DISABLED_CONFIG_ENTRY)


@callback
def async_cleanup(
    hass: HomeAssistant,
    dev_reg: DeviceRegistry,
    ent_reg: entity_registry.EntityRegistry,
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

    # Periodic purge of orphaned devices to avoid the registry
    # growing without bounds when there are lots of deleted devices
    dev_reg.async_purge_expired_orphaned_devices()


@callback
def async_setup_cleanup(hass: HomeAssistant, dev_reg: DeviceRegistry) -> None:
    """Clean up device registry when entities removed."""
    from . import entity_registry  # pylint: disable=import-outside-toplevel

    async def cleanup() -> None:
        """Cleanup."""
        ent_reg = await entity_registry.async_get_registry(hass)
        async_cleanup(hass, dev_reg, ent_reg)

    debounced_cleanup = Debouncer(
        hass, _LOGGER, cooldown=CLEANUP_DELAY, immediate=False, function=cleanup
    )

    async def entity_registry_changed(event: Event) -> None:
        """Handle entity updated or removed dispatch."""
        await debounced_cleanup.async_call()

    @callback
    def entity_registry_changed_filter(event: Event) -> bool:
        """Handle entity updated or removed filter."""
        if (
            event.data["action"] == "update"
            and "device_id" not in event.data["changes"]
        ) or event.data["action"] == "create":
            return False

        return True

    if hass.is_running:
        hass.bus.async_listen(
            entity_registry.EVENT_ENTITY_REGISTRY_UPDATED,
            entity_registry_changed,
            event_filter=entity_registry_changed_filter,
        )
        return

    async def startup_clean(event: Event) -> None:
        """Clean up on startup."""
        hass.bus.async_listen(
            entity_registry.EVENT_ENTITY_REGISTRY_UPDATED,
            entity_registry_changed,
            event_filter=entity_registry_changed_filter,
        )
        await debounced_cleanup.async_call()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, startup_clean)


def _normalize_connections(connections: set[tuple[str, str]]) -> set[tuple[str, str]]:
    """Normalize connections to ensure we can match mac addresses."""
    return {
        (key, format_mac(value)) if key == CONNECTION_NETWORK_MAC else (key, value)
        for key, value in connections
    }


def _add_device_to_index(
    devices_index: _DeviceIndex,
    device: DeviceEntry | DeletedDeviceEntry,
) -> None:
    """Add a device to the index."""
    for identifier in device.identifiers:
        devices_index.identifiers[identifier] = device.id
    for connection in device.connections:
        devices_index.connections[connection] = device.id


def _remove_device_from_index(
    devices_index: _DeviceIndex,
    device: DeviceEntry | DeletedDeviceEntry,
) -> None:
    """Remove a device from the index."""
    for identifier in device.identifiers:
        if identifier in devices_index.identifiers:
            del devices_index.identifiers[identifier]
    for connection in device.connections:
        if connection in devices_index.connections:
            del devices_index.connections[connection]
