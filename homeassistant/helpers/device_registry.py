"""Provide a way to connect entities belonging to one device."""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from functools import cached_property, lru_cache, partial
import logging
import time
from typing import TYPE_CHECKING, Any, Literal, TypedDict, TypeVar

import attr
from yarl import URL

from homeassistant.const import EVENT_HOMEASSISTANT_STARTED, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import (
    Event,
    HomeAssistant,
    ReleaseChannel,
    callback,
    get_release_channel,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.loader import async_suggest_report_issue
from homeassistant.util.event_type import EventType
from homeassistant.util.hass_dict import HassKey
from homeassistant.util.json import format_unserializable_data
import homeassistant.util.uuid as uuid_util

from . import storage, translation
from .debounce import Debouncer
from .deprecation import (
    DeprecatedConstantEnum,
    all_with_deprecated_constants,
    check_if_deprecated_constant,
    dir_with_deprecated_constants,
)
from .frame import report
from .json import JSON_DUMP, find_paths_unserializable_data, json_bytes, json_fragment
from .registry import BaseRegistry, BaseRegistryItems
from .singleton import singleton
from .typing import UNDEFINED, UndefinedType

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

    from . import entity_registry

_LOGGER = logging.getLogger(__name__)

DATA_REGISTRY: HassKey[DeviceRegistry] = HassKey("device_registry")
EVENT_DEVICE_REGISTRY_UPDATED: EventType[EventDeviceRegistryUpdatedData] = EventType(
    "device_registry_updated"
)
STORAGE_KEY = "core.device_registry"
STORAGE_VERSION_MAJOR = 1
STORAGE_VERSION_MINOR = 5

CLEANUP_DELAY = 10

CONNECTION_BLUETOOTH = "bluetooth"
CONNECTION_NETWORK_MAC = "mac"
CONNECTION_UPNP = "upnp"
CONNECTION_ZIGBEE = "zigbee"

ORPHANED_DEVICE_KEEP_SECONDS = 86400 * 30

RUNTIME_ONLY_ATTRS = {"suggested_area"}

CONFIGURATION_URL_SCHEMES = {"http", "https", "homeassistant"}


class DeviceEntryDisabler(StrEnum):
    """What disabled a device entry."""

    CONFIG_ENTRY = "config_entry"
    INTEGRATION = "integration"
    USER = "user"


# DISABLED_* are deprecated, to be removed in 2022.3
_DEPRECATED_DISABLED_CONFIG_ENTRY = DeprecatedConstantEnum(
    DeviceEntryDisabler.CONFIG_ENTRY, "2025.1"
)
_DEPRECATED_DISABLED_INTEGRATION = DeprecatedConstantEnum(
    DeviceEntryDisabler.INTEGRATION, "2025.1"
)
_DEPRECATED_DISABLED_USER = DeprecatedConstantEnum(DeviceEntryDisabler.USER, "2025.1")


class DeviceInfo(TypedDict, total=False):
    """Entity device information for device registry."""

    configuration_url: str | URL | None
    connections: set[tuple[str, str]]
    default_manufacturer: str
    default_model: str
    default_name: str
    entry_type: DeviceEntryType | None
    identifiers: set[tuple[str, str]]
    manufacturer: str | None
    model: str | None
    name: str | None
    serial_number: str | None
    suggested_area: str | None
    sw_version: str | None
    hw_version: str | None
    translation_key: str | None
    translation_placeholders: Mapping[str, str] | None
    via_device: tuple[str, str]


DEVICE_INFO_TYPES = {
    # Device info is categorized by finding the first device info type which has all
    # the keys of the device info. The link device info type must be kept first
    # to make it preferred over primary.
    "link": {
        "connections",
        "identifiers",
    },
    "primary": {
        "configuration_url",
        "connections",
        "entry_type",
        "hw_version",
        "identifiers",
        "manufacturer",
        "model",
        "name",
        "serial_number",
        "suggested_area",
        "sw_version",
        "via_device",
    },
    "secondary": {
        "connections",
        "default_manufacturer",
        "default_model",
        "default_name",
        # Used by Fritz
        "via_device",
    },
}

DEVICE_INFO_KEYS = set.union(*(itm for itm in DEVICE_INFO_TYPES.values()))


class _EventDeviceRegistryUpdatedData_CreateRemove(TypedDict):
    """EventDeviceRegistryUpdated data for action type 'create' and 'remove'."""

    action: Literal["create", "remove"]
    device_id: str


class _EventDeviceRegistryUpdatedData_Update(TypedDict):
    """EventDeviceRegistryUpdated data for action type 'update'."""

    action: Literal["update"]
    device_id: str
    changes: dict[str, Any]


EventDeviceRegistryUpdatedData = (
    _EventDeviceRegistryUpdatedData_CreateRemove
    | _EventDeviceRegistryUpdatedData_Update
)


class DeviceEntryType(StrEnum):
    """Device entry type."""

    SERVICE = "service"


class DeviceInfoError(HomeAssistantError):
    """Raised when device info is invalid."""

    def __init__(self, domain: str, device_info: DeviceInfo, message: str) -> None:
        """Initialize error."""
        super().__init__(
            f"Invalid device info {device_info} for '{domain}' config entry: {message}",
        )
        self.device_info = device_info
        self.domain = domain


def _validate_device_info(
    config_entry: ConfigEntry,
    device_info: DeviceInfo,
) -> str:
    """Process a device info."""
    keys = set(device_info)

    # If no keys or not enough info to match up, abort
    if not device_info.get("connections") and not device_info.get("identifiers"):
        raise DeviceInfoError(
            config_entry.domain,
            device_info,
            "device info must include at least one of identifiers or connections",
        )

    device_info_type: str | None = None

    # Find the first device info type which has all keys in the device info
    for possible_type, allowed_keys in DEVICE_INFO_TYPES.items():
        if keys <= allowed_keys:
            device_info_type = possible_type
            break

    if device_info_type is None:
        raise DeviceInfoError(
            config_entry.domain,
            device_info,
            (
                "device info needs to either describe a device, "
                "link to existing device or provide extra information."
            ),
        )

    return device_info_type


_cached_parse_url = lru_cache(maxsize=512)(URL)
"""Parse a URL and cache the result."""


def _validate_configuration_url(value: Any) -> str | None:
    """Validate and convert configuration_url."""
    if value is None:
        return None

    url_as_str = str(value)
    url = value if type(value) is URL else _cached_parse_url(url_as_str)

    if url.scheme not in CONFIGURATION_URL_SCHEMES or not url.host:
        raise ValueError(f"invalid configuration_url '{value}'")

    return url_as_str


@attr.s(frozen=True)
class DeviceEntry:
    """Device Registry Entry."""

    area_id: str | None = attr.ib(default=None)
    config_entries: set[str] = attr.ib(converter=set, factory=set)
    configuration_url: str | None = attr.ib(default=None)
    connections: set[tuple[str, str]] = attr.ib(converter=set, factory=set)
    disabled_by: DeviceEntryDisabler | None = attr.ib(default=None)
    entry_type: DeviceEntryType | None = attr.ib(default=None)
    hw_version: str | None = attr.ib(default=None)
    id: str = attr.ib(factory=uuid_util.random_uuid_hex)
    identifiers: set[tuple[str, str]] = attr.ib(converter=set, factory=set)
    labels: set[str] = attr.ib(converter=set, factory=set)
    manufacturer: str | None = attr.ib(default=None)
    model: str | None = attr.ib(default=None)
    name_by_user: str | None = attr.ib(default=None)
    name: str | None = attr.ib(default=None)
    serial_number: str | None = attr.ib(default=None)
    suggested_area: str | None = attr.ib(default=None)
    sw_version: str | None = attr.ib(default=None)
    via_device_id: str | None = attr.ib(default=None)
    # This value is not stored, just used to keep track of events to fire.
    is_new: bool = attr.ib(default=False)

    @property
    def disabled(self) -> bool:
        """Return if entry is disabled."""
        return self.disabled_by is not None

    @property
    def dict_repr(self) -> dict[str, Any]:
        """Return a dict representation of the entry."""
        # Convert sets and tuples to lists
        # so the JSON serializer does not have to do
        # it every time
        return {
            "area_id": self.area_id,
            "configuration_url": self.configuration_url,
            "config_entries": list(self.config_entries),
            "connections": list(self.connections),
            "disabled_by": self.disabled_by,
            "entry_type": self.entry_type,
            "hw_version": self.hw_version,
            "id": self.id,
            "identifiers": list(self.identifiers),
            "labels": list(self.labels),
            "manufacturer": self.manufacturer,
            "model": self.model,
            "name_by_user": self.name_by_user,
            "name": self.name,
            "serial_number": self.serial_number,
            "sw_version": self.sw_version,
            "via_device_id": self.via_device_id,
        }

    @cached_property
    def json_repr(self) -> bytes | None:
        """Return a cached JSON representation of the entry."""
        try:
            dict_repr = self.dict_repr
            return json_bytes(dict_repr)
        except (ValueError, TypeError):
            _LOGGER.error(
                "Unable to serialize entry %s to JSON. Bad data found at %s",
                self.id,
                format_unserializable_data(
                    find_paths_unserializable_data(dict_repr, dump=JSON_DUMP)
                ),
            )
        return None

    @cached_property
    def as_storage_fragment(self) -> json_fragment:
        """Return a json fragment for storage."""
        return json_fragment(
            json_bytes(
                {
                    "area_id": self.area_id,
                    "config_entries": list(self.config_entries),
                    "configuration_url": self.configuration_url,
                    "connections": list(self.connections),
                    "disabled_by": self.disabled_by,
                    "entry_type": self.entry_type,
                    "hw_version": self.hw_version,
                    "id": self.id,
                    "identifiers": list(self.identifiers),
                    "labels": list(self.labels),
                    "manufacturer": self.manufacturer,
                    "model": self.model,
                    "name_by_user": self.name_by_user,
                    "name": self.name,
                    "serial_number": self.serial_number,
                    "sw_version": self.sw_version,
                    "via_device_id": self.via_device_id,
                }
            )
        )


@attr.s(frozen=True)
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

    @cached_property
    def as_storage_fragment(self) -> json_fragment:
        """Return a json fragment for storage."""
        return json_fragment(
            json_bytes(
                {
                    "config_entries": list(self.config_entries),
                    "connections": list(self.connections),
                    "identifiers": list(self.identifiers),
                    "id": self.id,
                    "orphaned_timestamp": self.orphaned_timestamp,
                }
            )
        )


@lru_cache(maxsize=512)
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


class DeviceRegistryStore(storage.Store[dict[str, list[dict[str, Any]]]]):
    """Store entity registry data."""

    async def _async_migrate_func(
        self,
        old_major_version: int,
        old_minor_version: int,
        old_data: dict[str, list[dict[str, Any]]],
    ) -> dict[str, Any]:
        """Migrate to the new version."""
        if old_major_version < 2:
            if old_minor_version < 2:
                # Version 1.2 implements migration and freezes the available keys,
                # populate keys which were introduced before version 1.2
                for device in old_data["devices"]:
                    device.setdefault("area_id", None)
                    device.setdefault("configuration_url", None)
                    device.setdefault("disabled_by", None)
                    try:
                        device["entry_type"] = DeviceEntryType(
                            device.get("entry_type"),  # type: ignore[arg-type]
                        )
                    except ValueError:
                        device["entry_type"] = None
                    device.setdefault("name_by_user", None)
                    # via_device_id was originally introduced as hub_device_id
                    device.setdefault("via_device_id", device.get("hub_device_id"))
                old_data.setdefault("deleted_devices", [])
                for device in old_data["deleted_devices"]:
                    device.setdefault("orphaned_timestamp", None)
            if old_minor_version < 3:
                # Version 1.3 adds hw_version
                for device in old_data["devices"]:
                    device["hw_version"] = None
            if old_minor_version < 4:
                # Introduced in 2023.11
                for device in old_data["devices"]:
                    device["serial_number"] = None
            if old_minor_version < 5:
                # Introduced in 2024.3
                for device in old_data["devices"]:
                    device["labels"] = device.get("labels", [])

        if old_major_version > 1:
            raise NotImplementedError
        return old_data


_EntryTypeT = TypeVar("_EntryTypeT", DeviceEntry, DeletedDeviceEntry)


class DeviceRegistryItems(BaseRegistryItems[_EntryTypeT]):
    """Container for device registry items, maps device id -> entry.

    Maintains two additional indexes:
    - (connection_type, connection identifier) -> entry
    - (DOMAIN, identifier) -> entry
    """

    def __init__(self) -> None:
        """Initialize the container."""
        super().__init__()
        self._connections: dict[tuple[str, str], _EntryTypeT] = {}
        self._identifiers: dict[tuple[str, str], _EntryTypeT] = {}

    def _index_entry(self, key: str, entry: _EntryTypeT) -> None:
        """Index an entry."""
        for connection in entry.connections:
            self._connections[connection] = entry
        for identifier in entry.identifiers:
            self._identifiers[identifier] = entry

    def _unindex_entry(
        self, key: str, replacement_entry: _EntryTypeT | None = None
    ) -> None:
        """Unindex an entry."""
        old_entry = self.data[key]
        for connection in old_entry.connections:
            del self._connections[connection]
        for identifier in old_entry.identifiers:
            del self._identifiers[identifier]

    def get_entry(
        self,
        identifiers: set[tuple[str, str]] | None,
        connections: set[tuple[str, str]] | None,
    ) -> _EntryTypeT | None:
        """Get entry from identifiers or connections."""
        if identifiers:
            for identifier in identifiers:
                if identifier in self._identifiers:
                    return self._identifiers[identifier]
        if not connections:
            return None
        for connection in _normalize_connections(connections):
            if connection in self._connections:
                return self._connections[connection]
        return None


class ActiveDeviceRegistryItems(DeviceRegistryItems[DeviceEntry]):
    """Container for active (non-deleted) device registry entries."""

    def __init__(self) -> None:
        """Initialize the container.

        Maintains three additional indexes:

        - area_id -> dict[key, True]
        - config_entry_id -> dict[key, True]
        - label -> dict[key, True]
        """
        super().__init__()
        self._area_id_index: dict[str, dict[str, Literal[True]]] = {}
        self._config_entry_id_index: dict[str, dict[str, Literal[True]]] = {}
        self._labels_index: dict[str, dict[str, Literal[True]]] = {}

    def _index_entry(self, key: str, entry: DeviceEntry) -> None:
        """Index an entry."""
        super()._index_entry(key, entry)
        if (area_id := entry.area_id) is not None:
            self._area_id_index.setdefault(area_id, {})[key] = True
        for label in entry.labels:
            self._labels_index.setdefault(label, {})[key] = True
        for config_entry_id in entry.config_entries:
            self._config_entry_id_index.setdefault(config_entry_id, {})[key] = True

    def _unindex_entry(
        self, key: str, replacement_entry: DeviceEntry | None = None
    ) -> None:
        """Unindex an entry."""
        entry = self.data[key]
        if area_id := entry.area_id:
            self._unindex_entry_value(key, area_id, self._area_id_index)
        if labels := entry.labels:
            for label in labels:
                self._unindex_entry_value(key, label, self._labels_index)
        for config_entry_id in entry.config_entries:
            self._unindex_entry_value(key, config_entry_id, self._config_entry_id_index)
        super()._unindex_entry(key, replacement_entry)

    def get_devices_for_area_id(self, area_id: str) -> list[DeviceEntry]:
        """Get devices for area."""
        data = self.data
        return [data[key] for key in self._area_id_index.get(area_id, ())]

    def get_devices_for_label(self, label: str) -> list[DeviceEntry]:
        """Get devices for label."""
        data = self.data
        return [data[key] for key in self._labels_index.get(label, ())]

    def get_devices_for_config_entry_id(
        self, config_entry_id: str
    ) -> list[DeviceEntry]:
        """Get devices for config entry."""
        data = self.data
        return [
            data[key] for key in self._config_entry_id_index.get(config_entry_id, ())
        ]


class DeviceRegistry(BaseRegistry[dict[str, list[dict[str, Any]]]]):
    """Class to hold a registry of devices."""

    devices: ActiveDeviceRegistryItems
    deleted_devices: DeviceRegistryItems[DeletedDeviceEntry]
    _device_data: dict[str, DeviceEntry]

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the device registry."""
        self.hass = hass
        self._store = DeviceRegistryStore(
            hass,
            STORAGE_VERSION_MAJOR,
            STORAGE_KEY,
            atomic_writes=True,
            minor_version=STORAGE_VERSION_MINOR,
        )

    @callback
    def async_get(self, device_id: str) -> DeviceEntry | None:
        """Get device.

        We retrieve the DeviceEntry from the underlying dict to avoid
        the overhead of the UserDict __getitem__.
        """
        return self._device_data.get(device_id)

    @callback
    def async_get_device(
        self,
        identifiers: set[tuple[str, str]] | None = None,
        connections: set[tuple[str, str]] | None = None,
    ) -> DeviceEntry | None:
        """Check if device is registered."""
        return self.devices.get_entry(identifiers, connections)

    def _async_get_deleted_device(
        self,
        identifiers: set[tuple[str, str]],
        connections: set[tuple[str, str]],
    ) -> DeletedDeviceEntry | None:
        """Check if device is deleted."""
        return self.deleted_devices.get_entry(identifiers, connections)

    def _substitute_name_placeholders(
        self,
        domain: str,
        name: str,
        translation_placeholders: Mapping[str, str],
    ) -> str:
        """Substitute placeholders in entity name."""
        try:
            return name.format(**translation_placeholders)
        except KeyError as err:
            if get_release_channel() is not ReleaseChannel.STABLE:
                raise HomeAssistantError(f"Missing placeholder {err}") from err
            report_issue = async_suggest_report_issue(
                self.hass, integration_domain=domain
            )
            _LOGGER.warning(
                (
                    "Device from integration %s has translation placeholders '%s' "
                    "which do not match the name '%s', please %s"
                ),
                domain,
                translation_placeholders,
                name,
                report_issue,
            )
            return name

    @callback
    def async_get_or_create(
        self,
        *,
        config_entry_id: str,
        configuration_url: str | URL | None | UndefinedType = UNDEFINED,
        connections: set[tuple[str, str]] | None | UndefinedType = UNDEFINED,
        default_manufacturer: str | None | UndefinedType = UNDEFINED,
        default_model: str | None | UndefinedType = UNDEFINED,
        default_name: str | None | UndefinedType = UNDEFINED,
        # To disable a device if it gets created
        disabled_by: DeviceEntryDisabler | None | UndefinedType = UNDEFINED,
        entry_type: DeviceEntryType | None | UndefinedType = UNDEFINED,
        hw_version: str | None | UndefinedType = UNDEFINED,
        identifiers: set[tuple[str, str]] | None | UndefinedType = UNDEFINED,
        manufacturer: str | None | UndefinedType = UNDEFINED,
        model: str | None | UndefinedType = UNDEFINED,
        name: str | None | UndefinedType = UNDEFINED,
        serial_number: str | None | UndefinedType = UNDEFINED,
        suggested_area: str | None | UndefinedType = UNDEFINED,
        sw_version: str | None | UndefinedType = UNDEFINED,
        translation_key: str | None = None,
        translation_placeholders: Mapping[str, str] | None = None,
        via_device: tuple[str, str] | None | UndefinedType = UNDEFINED,
    ) -> DeviceEntry:
        """Get device. Create if it doesn't exist."""
        if configuration_url is not UNDEFINED:
            configuration_url = _validate_configuration_url(configuration_url)

        config_entry = self.hass.config_entries.async_get_entry(config_entry_id)
        if config_entry is None:
            raise HomeAssistantError(
                f"Can't link device to unknown config entry {config_entry_id}"
            )

        if translation_key:
            full_translation_key = (
                f"component.{config_entry.domain}.device.{translation_key}.name"
            )
            translations = translation.async_get_cached_translations(
                self.hass, self.hass.config.language, "device", config_entry.domain
            )
            translated_name = translations.get(full_translation_key, translation_key)
            name = self._substitute_name_placeholders(
                config_entry.domain, translated_name, translation_placeholders or {}
            )

        # Reconstruct a DeviceInfo dict from the arguments.
        # When we upgrade to Python 3.12, we can change this method to instead
        # accept kwargs typed as a DeviceInfo dict (PEP 692)
        device_info: DeviceInfo = {  # type: ignore[assignment]
            key: val
            for key, val in (
                ("configuration_url", configuration_url),
                ("connections", connections),
                ("default_manufacturer", default_manufacturer),
                ("default_model", default_model),
                ("default_name", default_name),
                ("entry_type", entry_type),
                ("hw_version", hw_version),
                ("identifiers", identifiers),
                ("manufacturer", manufacturer),
                ("model", model),
                ("name", name),
                ("serial_number", serial_number),
                ("suggested_area", suggested_area),
                ("sw_version", sw_version),
                ("via_device", via_device),
            )
            if val is not UNDEFINED
        }

        device_info_type = _validate_device_info(config_entry, device_info)

        if identifiers is None or identifiers is UNDEFINED:
            identifiers = set()

        if connections is None or connections is UNDEFINED:
            connections = set()
        else:
            connections = _normalize_connections(connections)

        device = self.async_get_device(identifiers=identifiers, connections=connections)

        if device is None:
            deleted_device = self._async_get_deleted_device(identifiers, connections)
            if deleted_device is None:
                device = DeviceEntry(is_new=True)
            else:
                self.deleted_devices.pop(deleted_device.id)
                device = deleted_device.to_device_entry(
                    config_entry_id, connections, identifiers
                )
            self.devices[device.id] = device
            # If creating a new device, default to the config entry name
            if device_info_type == "primary" and (not name or name is UNDEFINED):
                name = config_entry.title

        if default_manufacturer is not UNDEFINED and device.manufacturer is None:
            manufacturer = default_manufacturer

        if default_model is not UNDEFINED and device.model is None:
            model = default_model

        if default_name is not UNDEFINED and device.name is None:
            name = default_name

        if via_device is not None and via_device is not UNDEFINED:
            via = self.async_get_device(identifiers={via_device})
            via_device_id: str | UndefinedType = via.id if via else UNDEFINED
        else:
            via_device_id = UNDEFINED

        if isinstance(entry_type, str) and not isinstance(entry_type, DeviceEntryType):
            report(  # type: ignore[unreachable]
                (
                    "uses str for device registry entry_type. This is deprecated and"
                    " will stop working in Home Assistant 2022.3, it should be updated"
                    " to use DeviceEntryType instead"
                ),
                error_if_core=False,
            )
            entry_type = DeviceEntryType(entry_type)

        device = self.async_update_device(
            device.id,
            add_config_entry_id=config_entry_id,
            configuration_url=configuration_url,
            disabled_by=disabled_by,
            entry_type=entry_type,
            hw_version=hw_version,
            manufacturer=manufacturer,
            merge_connections=connections or UNDEFINED,
            merge_identifiers=identifiers or UNDEFINED,
            model=model,
            name=name,
            serial_number=serial_number,
            suggested_area=suggested_area,
            sw_version=sw_version,
            via_device_id=via_device_id,
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
        add_config_entry_id: str | UndefinedType = UNDEFINED,
        area_id: str | None | UndefinedType = UNDEFINED,
        configuration_url: str | URL | None | UndefinedType = UNDEFINED,
        disabled_by: DeviceEntryDisabler | None | UndefinedType = UNDEFINED,
        entry_type: DeviceEntryType | None | UndefinedType = UNDEFINED,
        hw_version: str | None | UndefinedType = UNDEFINED,
        labels: set[str] | UndefinedType = UNDEFINED,
        manufacturer: str | None | UndefinedType = UNDEFINED,
        merge_connections: set[tuple[str, str]] | UndefinedType = UNDEFINED,
        merge_identifiers: set[tuple[str, str]] | UndefinedType = UNDEFINED,
        model: str | None | UndefinedType = UNDEFINED,
        name_by_user: str | None | UndefinedType = UNDEFINED,
        name: str | None | UndefinedType = UNDEFINED,
        new_identifiers: set[tuple[str, str]] | UndefinedType = UNDEFINED,
        remove_config_entry_id: str | UndefinedType = UNDEFINED,
        serial_number: str | None | UndefinedType = UNDEFINED,
        suggested_area: str | None | UndefinedType = UNDEFINED,
        sw_version: str | None | UndefinedType = UNDEFINED,
        via_device_id: str | None | UndefinedType = UNDEFINED,
    ) -> DeviceEntry | None:
        """Update device attributes."""
        old = self.devices[device_id]

        new_values: dict[str, Any] = {}  # Dict with new key/value pairs
        old_values: dict[str, Any] = {}  # Dict with old key/value pairs

        config_entries = old.config_entries

        if merge_identifiers is not UNDEFINED and new_identifiers is not UNDEFINED:
            raise HomeAssistantError

        if isinstance(disabled_by, str) and not isinstance(
            disabled_by, DeviceEntryDisabler
        ):
            report(  # type: ignore[unreachable]
                (
                    "uses str for device registry disabled_by. This is deprecated and"
                    " will stop working in Home Assistant 2022.3, it should be updated"
                    " to use DeviceEntryDisabler instead"
                ),
                error_if_core=False,
            )
            disabled_by = DeviceEntryDisabler(disabled_by)

        if (
            suggested_area is not None
            and suggested_area is not UNDEFINED
            and suggested_area != ""
            and area_id is UNDEFINED
            and old.area_id is None
        ):
            # Circular dep
            # pylint: disable-next=import-outside-toplevel
            from . import area_registry as ar

            area = ar.async_get(self.hass).async_get_or_create(suggested_area)
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
            new_values["config_entries"] = config_entries
            old_values["config_entries"] = old.config_entries

        for attr_name, setvalue in (
            ("connections", merge_connections),
            ("identifiers", merge_identifiers),
        ):
            old_value = getattr(old, attr_name)
            # If not undefined, check if `value` contains new items.
            if setvalue is not UNDEFINED and not setvalue.issubset(old_value):
                new_values[attr_name] = old_value | setvalue
                old_values[attr_name] = old_value

        if new_identifiers is not UNDEFINED:
            new_values["identifiers"] = new_identifiers
            old_values["identifiers"] = old.identifiers

        if configuration_url is not UNDEFINED:
            configuration_url = _validate_configuration_url(configuration_url)

        for attr_name, value in (
            ("area_id", area_id),
            ("configuration_url", configuration_url),
            ("disabled_by", disabled_by),
            ("entry_type", entry_type),
            ("hw_version", hw_version),
            ("labels", labels),
            ("manufacturer", manufacturer),
            ("model", model),
            ("name", name),
            ("name_by_user", name_by_user),
            ("serial_number", serial_number),
            ("suggested_area", suggested_area),
            ("sw_version", sw_version),
            ("via_device_id", via_device_id),
        ):
            if value is not UNDEFINED and value != getattr(old, attr_name):
                new_values[attr_name] = value
                old_values[attr_name] = getattr(old, attr_name)

        if old.is_new:
            new_values["is_new"] = False

        if not new_values:
            return old

        self.hass.verify_event_loop_thread("async_update_device")
        new = attr.evolve(old, **new_values)
        self.devices[device_id] = new

        # If its only run time attributes (suggested_area)
        # that do not get saved we do not want to write
        # to disk or fire an event as we would end up
        # firing events for data we have nothing to compare
        # against since its never saved on disk
        if RUNTIME_ONLY_ATTRS.issuperset(new_values):
            return new

        self.async_schedule_save()

        data: EventDeviceRegistryUpdatedData
        if old.is_new:
            data = {"action": "create", "device_id": new.id}
        else:
            data = {"action": "update", "device_id": new.id, "changes": old_values}

        self.hass.bus.async_fire_internal(EVENT_DEVICE_REGISTRY_UPDATED, data)

        return new

    @callback
    def async_remove_device(self, device_id: str) -> None:
        """Remove a device from the device registry."""
        self.hass.verify_event_loop_thread("async_remove_device")
        device = self.devices.pop(device_id)
        self.deleted_devices[device_id] = DeletedDeviceEntry(
            config_entries=device.config_entries,
            connections=device.connections,
            identifiers=device.identifiers,
            id=device.id,
            orphaned_timestamp=None,
        )
        for other_device in list(self.devices.values()):
            if other_device.via_device_id == device_id:
                self.async_update_device(other_device.id, via_device_id=None)
        self.hass.bus.async_fire_internal(
            EVENT_DEVICE_REGISTRY_UPDATED,
            _EventDeviceRegistryUpdatedData_CreateRemove(
                action="remove", device_id=device_id
            ),
        )
        self.async_schedule_save()

    async def async_load(self) -> None:
        """Load the device registry."""
        async_setup_cleanup(self.hass, self)

        data = await self._store.async_load()

        devices = ActiveDeviceRegistryItems()
        deleted_devices: DeviceRegistryItems[DeletedDeviceEntry] = DeviceRegistryItems()

        if data is not None:
            for device in data["devices"]:
                devices[device["id"]] = DeviceEntry(
                    area_id=device["area_id"],
                    config_entries=set(device["config_entries"]),
                    configuration_url=device["configuration_url"],
                    # type ignores (if tuple arg was cast): likely https://github.com/python/mypy/issues/8625
                    connections={
                        tuple(conn)  # type: ignore[misc]
                        for conn in device["connections"]
                    },
                    disabled_by=(
                        DeviceEntryDisabler(device["disabled_by"])
                        if device["disabled_by"]
                        else None
                    ),
                    entry_type=(
                        DeviceEntryType(device["entry_type"])
                        if device["entry_type"]
                        else None
                    ),
                    hw_version=device["hw_version"],
                    id=device["id"],
                    identifiers={
                        tuple(iden)  # type: ignore[misc]
                        for iden in device["identifiers"]
                    },
                    labels=set(device["labels"]),
                    manufacturer=device["manufacturer"],
                    model=device["model"],
                    name_by_user=device["name_by_user"],
                    name=device["name"],
                    serial_number=device["serial_number"],
                    sw_version=device["sw_version"],
                    via_device_id=device["via_device_id"],
                )
            # Introduced in 0.111
            for device in data["deleted_devices"]:
                deleted_devices[device["id"]] = DeletedDeviceEntry(
                    config_entries=set(device["config_entries"]),
                    connections={tuple(conn) for conn in device["connections"]},
                    identifiers={tuple(iden) for iden in device["identifiers"]},
                    id=device["id"],
                    orphaned_timestamp=device["orphaned_timestamp"],
                )

        self.devices = devices
        self.deleted_devices = deleted_devices
        self._device_data = devices.data

    @callback
    def _data_to_save(self) -> dict[str, Any]:
        """Return data of device registry to store in a file."""
        return {
            "devices": [entry.as_storage_fragment for entry in self.devices.values()],
            "deleted_devices": [
                entry.as_storage_fragment for entry in self.deleted_devices.values()
            ],
        }

    @callback
    def async_clear_config_entry(self, config_entry_id: str) -> None:
        """Clear config entry from registry entries."""
        now_time = time.time()
        for device in self.devices.get_devices_for_config_entry_id(config_entry_id):
            self.async_update_device(device.id, remove_config_entry_id=config_entry_id)
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
                del self.deleted_devices[deleted_device.id]

    @callback
    def async_clear_area_id(self, area_id: str) -> None:
        """Clear area id from registry entries."""
        for device in self.devices.get_devices_for_area_id(area_id):
            self.async_update_device(device.id, area_id=None)

    @callback
    def async_clear_label_id(self, label_id: str) -> None:
        """Clear label from registry entries."""
        for device in self.devices.get_devices_for_label(label_id):
            self.async_update_device(device.id, labels=device.labels - {label_id})


@callback
@singleton(DATA_REGISTRY)
def async_get(hass: HomeAssistant) -> DeviceRegistry:
    """Get device registry."""
    return DeviceRegistry(hass)


async def async_load(hass: HomeAssistant) -> None:
    """Load device registry."""
    assert DATA_REGISTRY not in hass.data
    await async_get(hass).async_load()


@callback
def async_entries_for_area(registry: DeviceRegistry, area_id: str) -> list[DeviceEntry]:
    """Return entries that match an area."""
    return registry.devices.get_devices_for_area_id(area_id)


@callback
def async_entries_for_label(
    registry: DeviceRegistry, label_id: str
) -> list[DeviceEntry]:
    """Return entries that match a label."""
    return registry.devices.get_devices_for_label(label_id)


@callback
def async_entries_for_config_entry(
    registry: DeviceRegistry, config_entry_id: str
) -> list[DeviceEntry]:
    """Return entries that match a config entry."""
    return registry.devices.get_devices_for_config_entry_id(config_entry_id)


@callback
def async_config_entry_disabled_by_changed(
    registry: DeviceRegistry, config_entry: ConfigEntry
) -> None:
    """Handle a config entry being disabled or enabled.

    Disable devices in the registry that are associated with a config entry when
    the config entry is disabled, enable devices in the registry that are associated
    with a config entry when the config entry is enabled and the devices are marked
    DeviceEntryDisabler.CONFIG_ENTRY.
    Only disable a device if all associated config entries are disabled.
    """

    devices = async_entries_for_config_entry(registry, config_entry.entry_id)

    if not config_entry.disabled_by:
        for device in devices:
            if device.disabled_by is not DeviceEntryDisabler.CONFIG_ENTRY:
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
        registry.async_update_device(
            device.id, disabled_by=DeviceEntryDisabler.CONFIG_ENTRY
        )


@callback
def async_cleanup(
    hass: HomeAssistant,
    dev_reg: DeviceRegistry,
    ent_reg: entity_registry.EntityRegistry,
) -> None:
    """Clean up device registry."""
    # Find all devices that are referenced by a config_entry.
    config_entry_ids = set(hass.config_entries.async_entry_ids())
    references_config_entries = {
        device.id
        for device in dev_reg.devices.values()
        for config_entry_id in device.config_entries
        if config_entry_id in config_entry_ids
    }

    # Find all devices that are referenced in the entity registry.
    device_ids_referenced_by_entities = set(ent_reg.entities.get_device_ids())

    orphan = (
        set(dev_reg.devices)
        - device_ids_referenced_by_entities
        - references_config_entries
    )

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
    # pylint: disable-next=import-outside-toplevel
    from . import entity_registry, label_registry as lr

    @callback
    def _label_removed_from_registry_filter(
        event_data: lr.EventLabelRegistryUpdatedData,
    ) -> bool:
        """Filter all except for the remove action from label registry events."""
        return event_data["action"] == "remove"

    @callback
    def _handle_label_registry_update(event: lr.EventLabelRegistryUpdated) -> None:
        """Update devices that have a label that has been removed."""
        dev_reg.async_clear_label_id(event.data["label_id"])

    hass.bus.async_listen(
        event_type=lr.EVENT_LABEL_REGISTRY_UPDATED,
        event_filter=_label_removed_from_registry_filter,
        listener=_handle_label_registry_update,
    )

    @callback
    def _async_cleanup() -> None:
        """Cleanup."""
        ent_reg = entity_registry.async_get(hass)
        async_cleanup(hass, dev_reg, ent_reg)

    debounced_cleanup: Debouncer[None] = Debouncer(
        hass, _LOGGER, cooldown=CLEANUP_DELAY, immediate=False, function=_async_cleanup
    )

    @callback
    def _async_entity_registry_changed(
        event: Event[entity_registry.EventEntityRegistryUpdatedData],
    ) -> None:
        """Handle entity updated or removed dispatch."""
        debounced_cleanup.async_schedule_call()

    @callback
    def entity_registry_changed_filter(
        event_data: entity_registry.EventEntityRegistryUpdatedData,
    ) -> bool:
        """Handle entity updated or removed filter."""
        if (
            event_data["action"] == "update"
            and "device_id" not in event_data["changes"]
        ) or event_data["action"] == "create":
            return False

        return True

    def _async_listen_for_cleanup() -> None:
        """Listen for entity registry changes."""
        hass.bus.async_listen(
            entity_registry.EVENT_ENTITY_REGISTRY_UPDATED,
            _async_entity_registry_changed,
            event_filter=entity_registry_changed_filter,
        )

    if hass.is_running:
        _async_listen_for_cleanup()
        return

    async def startup_clean(event: Event) -> None:
        """Clean up on startup."""
        _async_listen_for_cleanup()
        await debounced_cleanup.async_call()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, startup_clean)

    @callback
    def _on_homeassistant_stop(event: Event) -> None:
        """Cancel debounced cleanup."""
        debounced_cleanup.async_cancel()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _on_homeassistant_stop)


def _normalize_connections(connections: set[tuple[str, str]]) -> set[tuple[str, str]]:
    """Normalize connections to ensure we can match mac addresses."""
    return {
        (key, format_mac(value)) if key == CONNECTION_NETWORK_MAC else (key, value)
        for key, value in connections
    }


# These can be removed if no deprecated constant are in this module anymore
__getattr__ = partial(check_if_deprecated_constant, module_globals=globals())
__dir__ = partial(
    dir_with_deprecated_constants, module_globals_keys=[*globals().keys()]
)
__all__ = all_with_deprecated_constants(globals())
