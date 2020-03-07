"""Provide a way to connect entities belonging to one device."""
from asyncio import Event
from collections import OrderedDict
import logging
from typing import Any, Dict, List, Optional, cast
import uuid

import attr

from homeassistant.core import callback
from homeassistant.loader import bind_hass

from .typing import HomeAssistantType

# mypy: allow-untyped-calls, allow-untyped-defs, no-check-untyped-defs

_LOGGER = logging.getLogger(__name__)
_UNDEF = object()

DATA_REGISTRY = "device_registry"
EVENT_DEVICE_REGISTRY_UPDATED = "device_registry_updated"
STORAGE_KEY = "core.device_registry"
STORAGE_VERSION = 1
SAVE_DELAY = 10

CONNECTION_NETWORK_MAC = "mac"
CONNECTION_UPNP = "upnp"
CONNECTION_ZIGBEE = "zigbee"


@attr.s(slots=True, frozen=True)
class DeviceEntry:
    """Device Registry Entry."""

    config_entries = attr.ib(type=set, converter=set, default=attr.Factory(set))
    connections = attr.ib(type=set, converter=set, default=attr.Factory(set))
    identifiers = attr.ib(type=set, converter=set, default=attr.Factory(set))
    manufacturer = attr.ib(type=str, default=None)
    model = attr.ib(type=str, default=None)
    name = attr.ib(type=str, default=None)
    sw_version = attr.ib(type=str, default=None)
    via_device_id = attr.ib(type=str, default=None)
    area_id = attr.ib(type=str, default=None)
    name_by_user = attr.ib(type=str, default=None)
    id = attr.ib(type=str, default=attr.Factory(lambda: uuid.uuid4().hex))
    # This value is not stored, just used to keep track of events to fire.
    is_new = attr.ib(type=bool, default=False)


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
        )

    @callback
    def async_update_device(
        self,
        device_id,
        *,
        area_id=_UNDEF,
        name=_UNDEF,
        name_by_user=_UNDEF,
        new_identifiers=_UNDEF,
        via_device_id=_UNDEF,
        remove_config_entry_id=_UNDEF,
    ):
        """Update properties of a device."""
        return self._async_update_device(
            device_id,
            area_id=area_id,
            name=name,
            name_by_user=name_by_user,
            new_identifiers=new_identifiers,
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
        remove = []
        for dev_id, device in self.devices.items():
            if device.config_entries == {config_entry_id}:
                remove.append(dev_id)
            else:
                self._async_update_device(
                    dev_id, remove_config_entry_id=config_entry_id
                )
        for dev_id in remove:
            self.async_remove_device(dev_id)

    @callback
    def async_clear_area_id(self, area_id: str) -> None:
        """Clear area id from registry entries."""
        for dev_id, device in self.devices.items():
            if area_id == device.area_id:
                self._async_update_device(dev_id, area_id=None)


@bind_hass
async def async_get_registry(hass: HomeAssistantType) -> DeviceRegistry:
    """Return device registry instance."""
    reg_or_evt = hass.data.get(DATA_REGISTRY)

    if not reg_or_evt:
        evt = hass.data[DATA_REGISTRY] = Event()

        reg = DeviceRegistry(hass)
        await reg.async_load()

        hass.data[DATA_REGISTRY] = reg
        evt.set()
        return reg

    if isinstance(reg_or_evt, Event):
        evt = reg_or_evt
        await evt.wait()
        return cast(DeviceRegistry, hass.data.get(DATA_REGISTRY))

    return cast(DeviceRegistry, reg_or_evt)


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
