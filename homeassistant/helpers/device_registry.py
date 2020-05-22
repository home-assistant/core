"""Provide a way to connect entities belonging to one device."""
from collections import OrderedDict
import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Tuple
import uuid

import attr

from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import Event, callback

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


@attr.s(slots=True, frozen=True)
class DeviceEntry:
    """Device Registry Entry."""

    config_entries: Set[str] = attr.ib(converter=set, default=attr.Factory(set))
    connections: Set[Tuple[str, str]] = attr.ib(
        converter=set, default=attr.Factory(set)
    )
    identifiers: Set[Tuple[str, str]] = attr.ib(
        converter=set, default=attr.Factory(set)
    )
    manufacturer: str = attr.ib(default=None)
    model: str = attr.ib(default=None)
    name: str = attr.ib(default=None)
    sw_version: str = attr.ib(default=None)
    via_device_id: str = attr.ib(default=None)
    area_id: str = attr.ib(default=None)
    name_by_user: str = attr.ib(default=None)
    entry_type: str = attr.ib(default=None)
    id: str = attr.ib(default=attr.Factory(lambda: uuid.uuid4().hex))
    # This value is not stored, just used to keep track of events to fire.
    is_new: bool = attr.ib(default=False)


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

    def __init__(self, hass: HomeAssistantType) -> None:
        """Initialize the device registry."""
        self.hass = hass
        self._store = hass.helpers.storage.Store(STORAGE_VERSION, STORAGE_KEY)

    @callback
    def async_get(self, device_id: str) -> Optional[DeviceEntry]:
        """Get device."""
        return self.devices.get(device_id)

    @callback
    def async_get_device(
        self, identifiers: set, connections: set
    ) -> Optional[DeviceEntry]:
        """Check if device is registered."""
        for device in self.devices.values():
            if any(iden in device.identifiers for iden in identifiers) or any(
                conn in device.connections for conn in connections
            ):
                return device
        return None

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
        sw_version=_UNDEF,
        entry_type=_UNDEF,
        via_device=None,
    ):
        """Get device. Create if it doesn't exist."""
        if not identifiers and not connections:
            return None

        if identifiers is None:
            identifiers = set()

        if connections is None:
            connections = set()

        connections = {
            (key, format_mac(value)) if key == CONNECTION_NETWORK_MAC else (key, value)
            for key, value in connections
        }

        device = self.async_get_device(identifiers, connections)

        if device is None:
            device = DeviceEntry(is_new=True)
            self.devices[device.id] = device

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

        if config_entries is not old.config_entries:
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

        new = self.devices[device_id] = attr.evolve(old, **changes)
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
        del self.devices[device_id]
        self.hass.bus.async_fire(
            EVENT_DEVICE_REGISTRY_UPDATED, {"action": "remove", "device_id": device_id}
        )
        self.async_schedule_save()

    async def async_load(self):
        """Load the device registry."""
        async_setup_cleanup(self.hass, self)

        data = await self._store.async_load()

        devices = OrderedDict()

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
                )

        self.devices = devices

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
            }
            for entry in self.devices.values()
        ]

        return data

    @callback
    def async_clear_config_entry(self, config_entry_id: str) -> None:
        """Clear config entry from registry entries."""
        for device in list(self.devices.values()):
            self._async_update_device(device.id, remove_config_entry_id=config_entry_id)

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
    # Find all devices that are no longer referenced in the entity registry.
    referenced = {entry.device_id for entry in ent_reg.entities.values()}
    orphan = set(dev_reg.devices) - referenced

    for dev_id in orphan:
        dev_reg.async_remove_device(dev_id)

    # Find all referenced config entries that no longer exist
    # This shouldn't happen but have not been able to track down the bug :(
    config_entry_ids = {entry.entry_id for entry in hass.config_entries.async_entries()}

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
