"""Provide a way to connect entities belonging to one device."""

import asyncio
from collections import defaultdict
from collections.abc import Iterable, Mapping
import copy
from datetime import datetime
from enum import StrEnum
from functools import lru_cache
import logging
import time
from typing import TYPE_CHECKING, Any, Literal, TypedDict, Unpack, override

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
from homeassistant.util import uuid as uuid_util
from homeassistant.util.dt import utc_from_timestamp, utcnow
from homeassistant.util.event_type import EventType
from homeassistant.util.hass_dict import HassKey
from homeassistant.util.json import format_unserializable_data

from . import storage, translation
from .debounce import Debouncer
from .deprecation import deprecated_function
from .frame import ReportBehavior, report_usage
from .json import JSON_DUMP, find_paths_unserializable_data, json_bytes, json_fragment
from .registry import BaseRegistry, BaseRegistryItems, RegistryIndexType
from .typing import UNDEFINED, UndefinedType

if TYPE_CHECKING:
    # mypy cannot workout _cache Protocol with attrs
    from propcache.api import cached_property as under_cached_property

    from homeassistant.config_entries import ConfigEntry

    from . import entity_registry
else:
    from propcache.api import under_cached_property

_LOGGER = logging.getLogger(__name__)

DATA_REGISTRY: HassKey[DeviceRegistry] = HassKey("device_registry")
EVENT_DEVICE_REGISTRY_UPDATED: EventType[EventDeviceRegistryUpdatedData] = EventType(
    "device_registry_updated"
)
STORAGE_KEY = "core.device_registry"
STORAGE_VERSION_MAJOR = 1
STORAGE_VERSION_MINOR = 13

CLEANUP_DELAY = 10

CONNECTION_BLUETOOTH = "bluetooth"
CONNECTION_NETWORK_MAC = "mac"
CONNECTION_UPNP = "upnp"
CONNECTION_ZIGBEE = "zigbee"

ORPHANED_DEVICE_KEEP_SECONDS = 86400 * 30

# suggested_area can be removed when suggested_area is removed from DeviceEntry.
# pending_move can be removed once add_config_entry_id and remove_config_entry_id
# are removed from the device registry API.
RUNTIME_ONLY_ATTRS = {"suggested_area", "pending_move"}

CONFIGURATION_URL_SCHEMES = {"http", "https", "homeassistant"}


class DeviceEntryDisabler(StrEnum):
    """What disabled a device entry."""

    CONFIG_ENTRY = "config_entry"
    INTEGRATION = "integration"
    USER = "user"


class DeviceInfo(TypedDict, total=False):
    """Entity device information for device registry."""

    configuration_url: str | URL | None
    connections: set[tuple[str, str]]
    created_at: str
    default_manufacturer: str
    default_model: str
    default_name: str
    entry_type: DeviceEntryType | None
    identifiers: set[tuple[str, str]]
    manufacturer: str | None
    model: str | None
    model_id: str | None
    modified_at: str
    name: str | None
    serial_number: str | None
    suggested_area: str | None
    sw_version: str | None
    hw_version: str | None
    translation_key: str | None
    translation_placeholders: Mapping[str, str] | None
    via_device: tuple[str, str]  # Deprecated, use via_device_id instead
    via_device_id: str


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
        "model_id",
        "name",
        "serial_number",
        "suggested_area",
        "sw_version",
        "via_device",
        "via_device_id",
    },
    "secondary": {
        "connections",
        "default_manufacturer",
        "default_model",
        "default_name",
        # Used by Fritz
        "via_device",
        "via_device_id",
    },
}


class _EventDeviceRegistryUpdatedData_Create(TypedDict):
    """EventDeviceRegistryUpdated data for action type 'create'."""

    action: Literal["create"]
    device_id: str


class _EventDeviceRegistryUpdatedData_Remove(TypedDict):
    """EventDeviceRegistryUpdated data for action type 'remove'."""

    action: Literal["remove"]
    device_id: str
    device: dict[str, Any]


class _EventDeviceRegistryUpdatedData_Update(TypedDict):
    """EventDeviceRegistryUpdated data for action type 'update'."""

    action: Literal["update"]
    device_id: str
    changes: dict[str, Any]


type EventDeviceRegistryUpdatedData = (
    _EventDeviceRegistryUpdatedData_Create
    | _EventDeviceRegistryUpdatedData_Remove
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


class DeviceCollisionError(HomeAssistantError):
    """Raised when a device collision is detected."""


class DeviceIdentifierCollisionError(DeviceCollisionError):
    """Raised when a device identifier collision is detected."""

    def __init__(
        self, identifiers: set[tuple[str, str]], existing_device: DeviceEntry
    ) -> None:
        """Initialize error."""
        super().__init__(
            f"Identifiers {identifiers} already registered with {existing_device}"
        )


class DeviceConnectionCollisionError(DeviceCollisionError):
    """Raised when a device connection collision is detected."""

    def __init__(
        self, normalized_connections: set[tuple[str, str]], existing_device: DeviceEntry
    ) -> None:
        """Initialize error."""
        super().__init__(
            f"Connections {normalized_connections} "
            f"already registered with {existing_device}"
        )


def _determine_device_info_type(
    config_entry: ConfigEntry,
    device_info: DeviceInfo,
) -> str:
    """Determine the type of a device info."""
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


class _ValidatedDeviceInfoFields(TypedDict):
    """Device info fields validated on create and update."""

    configuration_url: str | URL | None | UndefinedType
    hw_version: str | None | UndefinedType
    manufacturer: str | None | UndefinedType
    model: str | None | UndefinedType
    model_id: str | None | UndefinedType
    serial_number: str | None | UndefinedType
    sw_version: str | None | UndefinedType


_cached_parse_url = lru_cache(maxsize=512)(URL)
"""Parse a URL and cache the result."""


def _validate_str(name: str, value: Any) -> str | None | UndefinedType:
    """Validate that a device registry string field has correct type."""
    if (
        value is UNDEFINED
        or value is None
        or type(value) is str  # fast path for exact str
        or isinstance(value, str)
    ):
        return value
    report_usage(
        f"passes a non-string value of type {type(value).__name__} "
        f"as {name} to the device registry",
        core_behavior=ReportBehavior.LOG,
        breaks_in_ha_version="2026.12.0",
    )
    return str(value)


def _validate_device_info_fields(
    **fields: Unpack[_ValidatedDeviceInfoFields],
) -> _ValidatedDeviceInfoFields:
    """Validate device-info field values."""
    configuration_url = fields["configuration_url"]
    url: URL | None = None
    if type(configuration_url) is URL:
        url = configuration_url
        configuration_url = str(configuration_url)
    else:
        configuration_url = _validate_str("configuration_url", configuration_url)
        if isinstance(configuration_url, str):
            url = _cached_parse_url(configuration_url)
    if url is not None and (
        url.scheme not in CONFIGURATION_URL_SCHEMES or not url.host
    ):
        raise ValueError(f"invalid configuration_url '{configuration_url}'")
    return {
        "configuration_url": configuration_url,
        "hw_version": _validate_str("hw_version", fields["hw_version"]),
        "manufacturer": _validate_str("manufacturer", fields["manufacturer"]),
        "model": _validate_str("model", fields["model"]),
        "model_id": _validate_str("model_id", fields["model_id"]),
        "serial_number": _validate_str("serial_number", fields["serial_number"]),
        "sw_version": _validate_str("sw_version", fields["sw_version"]),
    }


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


def _normalize_connections(
    connections: Iterable[tuple[str, str]],
) -> set[tuple[str, str]]:
    """Normalize connections to ensure we can match mac addresses."""
    return {
        (key, format_mac(value)) if key == CONNECTION_NETWORK_MAC else (key, value)
        for key, value in connections
    }


def _normalize_connections_validator(
    instance: Any,
    attribute: Any,
    connections: Iterable[tuple[str, str]],
) -> None:
    """Check connections normalization used as attrs validator."""
    for key, value in connections:
        if key == CONNECTION_NETWORK_MAC and format_mac(value) != value:
            raise ValueError(f"Invalid mac address format: {value}")


@attr.s(frozen=True, slots=True)
class DeviceEntry:
    """Device Registry Entry."""

    config_entry_id: str = attr.ib()

    area_id: str | None = attr.ib(default=None)
    config_subentry_id: str | None = attr.ib(default=None)
    configuration_url: str | None = attr.ib(default=None)
    connections: set[tuple[str, str]] = attr.ib(
        converter=set, factory=set, validator=_normalize_connections_validator
    )
    created_at: datetime = attr.ib(factory=utcnow)
    disabled_by: DeviceEntryDisabler | None = attr.ib(default=None)
    entry_type: DeviceEntryType | None = attr.ib(default=None)
    hw_version: str | None = attr.ib(default=None)
    id: str = attr.ib(factory=uuid_util.random_uuid_hex)
    identifiers: set[tuple[str, str]] = attr.ib(converter=set, factory=set)
    labels: set[str] = attr.ib(converter=set, factory=set)
    # composite_device_id is the id of the pre-migration composite device this device was
    # split from; composite_primary_config_entry is that composite's former
    # primary_config_entry, so a restored composite device can report it.
    # split_at records when the split happened.
    composite_device_id: str | None = attr.ib(default=None)
    composite_primary_config_entry: str | None = attr.ib(default=None)
    split_at: datetime | None = attr.ib(default=None)
    manufacturer: str | None = attr.ib(default=None)
    model: str | None = attr.ib(default=None)
    model_id: str | None = attr.ib(default=None)
    modified_at: datetime = attr.ib(factory=utcnow)
    name_by_user: str | None = attr.ib(default=None)
    name: str | None = attr.ib(default=None)
    # Set on devices created by splitting a pre-migration composite device. On the
    # owning integration's first re-registration, the identifiers and connections
    # copied from the composite are replaced with the ones the integration provides.
    # This flag and the identifier-replacement logic can be removed in HA Core 2027.8.
    has_composite_identifiers: bool = attr.ib(default=False)
    serial_number: str | None = attr.ib(default=None)
    # Suggested area is deprecated and will be removed from DeviceEntry in HA Core 2026.9.
    _suggested_area: str | None = attr.ib(default=None)
    sw_version: str | None = attr.ib(default=None)
    via_device_id: str | None = attr.ib(default=None)
    # Transient pending move target (config_entry_id, config_subentry_id) initiated by
    # add_config_entry_id and completed by a subsequent remove_config_entry_id. It is
    # never stored and is not part of equality. Can be removed in HA Core 2027.8.
    _pending_move: tuple[str, str | None] | None = attr.ib(default=None, eq=False)
    # Set only on the read-only composite device that async_get synthesizes on demand
    # for a pre-migration composite device id. It holds the union of the split
    # devices' config entries and subentries so callers see the pre-split device. It is
    # never stored and the composite is never added to the registry. Can be removed in
    # HA Core 2027.8.
    _composite_subentries: dict[str, set[str | None]] | None = attr.ib(
        default=None, eq=False
    )
    _cache: dict[str, Any] = attr.ib(factory=dict, eq=False, init=False)

    @property
    def config_entries(self) -> set[str]:
        """Return the config entries this device belongs to.

        Deprecated compatibility shim: a device now belongs to a single config
        entry, available as config_entry_id.
        """
        if self._composite_subentries is not None:
            return set(self._composite_subentries)
        return {self.config_entry_id}

    @property
    def config_entries_subentries(self) -> dict[str, set[str | None]]:
        """Return the config subentries this device belongs to.

        Deprecated compatibility shim: a device now belongs to a single config
        entry and subentry, available as config_entry_id and config_subentry_id.
        """
        if self._composite_subentries is not None:
            return {
                entry_id: set(subentries)
                for entry_id, subentries in self._composite_subentries.items()
            }
        return {self.config_entry_id: {self.config_subentry_id}}

    @property
    def primary_config_entry(self) -> str:
        """Return the primary config entry of this device.

        Deprecated compatibility shim: a device now belongs to a single config
        entry, available as config_entry_id, which is its primary config entry.

        For a restored composite device (synthesized on the fly by async_get for a
        pre-migration composite device id), this returns the composite's former
        primary_config_entry, which is recorded on the split devices during migration as
        composite_primary_config_entry.
        """
        return self.config_entry_id

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
            # config_entries and config_entries_subentries are deprecated and kept for
            # backwards compatibility, they can be removed in HA Core 2027.8
            "config_entries": [self.config_entry_id],
            "config_entries_subentries": {
                self.config_entry_id: [self.config_subentry_id]
            },
            "config_entry_id": self.config_entry_id,
            "config_subentry_id": self.config_subentry_id,
            "connections": list(self.connections),
            "created_at": self.created_at.timestamp(),
            "disabled_by": self.disabled_by,
            "entry_type": self.entry_type,
            "hw_version": self.hw_version,
            "id": self.id,
            "identifiers": list(self.identifiers),
            "labels": list(self.labels),
            "manufacturer": self.manufacturer,
            "model": self.model,
            "model_id": self.model_id,
            "modified_at": self.modified_at.timestamp(),
            "name_by_user": self.name_by_user,
            "name": self.name,
            "primary_config_entry": self.primary_config_entry,
            "serial_number": self.serial_number,
            "sw_version": self.sw_version,
            "via_device_id": self.via_device_id,
        }

    @under_cached_property
    def json_repr(self) -> bytes | None:
        """Return a cached JSON representation of the entry."""
        try:
            dict_repr = self.dict_repr
            return json_bytes(dict_repr)
        except ValueError, TypeError:
            _LOGGER.error(
                "Unable to serialize entry %s to JSON. Bad data found at %s",
                self.id,
                format_unserializable_data(
                    find_paths_unserializable_data(dict_repr, dump=JSON_DUMP)
                ),
            )
        return None

    @under_cached_property
    def as_storage_fragment(self) -> json_fragment:
        """Return a json fragment for storage."""
        return json_fragment(
            json_bytes(
                {
                    "area_id": self.area_id,
                    # config_entries and config_entries_subentries are deprecated and
                    # kept for backwards compatibility, they can be removed from the
                    # storage representation in HA Core 2027.8
                    "config_entries": [self.config_entry_id],
                    "config_entries_subentries": {
                        self.config_entry_id: [self.config_subentry_id]
                    },
                    "config_entry_id": self.config_entry_id,
                    "config_subentry_id": self.config_subentry_id,
                    "configuration_url": self.configuration_url,
                    "connections": list(self.connections),
                    "created_at": self.created_at,
                    "disabled_by": self.disabled_by,
                    "entry_type": self.entry_type,
                    "hw_version": self.hw_version,
                    "id": self.id,
                    "identifiers": list(self.identifiers),
                    "labels": list(self.labels),
                    "composite_device_id": self.composite_device_id,
                    "composite_primary_config_entry": (
                        self.composite_primary_config_entry
                    ),
                    "split_at": self.split_at,
                    "manufacturer": self.manufacturer,
                    "model": self.model,
                    "model_id": self.model_id,
                    "modified_at": self.modified_at,
                    "name_by_user": self.name_by_user,
                    "name": self.name,
                    "has_composite_identifiers": (self.has_composite_identifiers),
                    "primary_config_entry": self.primary_config_entry,
                    "serial_number": self.serial_number,
                    "sw_version": self.sw_version,
                    "via_device_id": self.via_device_id,
                }
            )
        )

    @property
    @deprecated_function(
        "code which ignores suggested_area", breaks_in_ha_version="2026.9"
    )
    def suggested_area(self) -> str | None:
        """Return the suggested area for this device entry."""
        return self._suggested_area


@attr.s(frozen=True, slots=True)
class DeletedDeviceEntry:
    """Deleted Device Registry Entry."""

    # config_entry_id is None for orphaned deleted devices, i.e. devices whose owning
    # config entry has been removed
    config_entry_id: str | None = attr.ib()
    config_subentry_id: str | None = attr.ib()

    area_id: str | None = attr.ib()
    connections: set[tuple[str, str]] = attr.ib(
        validator=_normalize_connections_validator
    )
    created_at: datetime = attr.ib()
    disabled_by: DeviceEntryDisabler | UndefinedType | None = attr.ib()
    id: str = attr.ib()
    identifiers: set[tuple[str, str]] = attr.ib()
    labels: set[str] = attr.ib()
    modified_at: datetime = attr.ib()
    name_by_user: str | None = attr.ib()
    orphaned_timestamp: float | None = attr.ib()
    _cache: dict[str, Any] = attr.ib(factory=dict, eq=False, init=False)

    @property
    def config_entries(self) -> set[str]:
        """Return the config entries this device belonged to.

        Deprecated compatibility shim; empty for orphaned deleted devices.
        """
        return {self.config_entry_id} if self.config_entry_id is not None else set()

    @property
    def config_entries_subentries(self) -> dict[str, set[str | None]]:
        """Return the config subentries this device belonged to.

        Deprecated compatibility shim; empty for orphaned deleted devices.
        """
        if self.config_entry_id is None:
            return {}
        return {self.config_entry_id: {self.config_subentry_id}}

    def to_device_entry(
        self,
        config_entry: ConfigEntry,
        config_subentry_id: str | None,
        connections: set[tuple[str, str]],
        identifiers: set[tuple[str, str]],
        disabled_by: DeviceEntryDisabler | UndefinedType | None,
    ) -> DeviceEntry:
        """Create DeviceEntry from DeletedDeviceEntry."""
        # Adjust disabled_by based on config entry state
        if self.disabled_by is not UNDEFINED:
            disabled_by = self.disabled_by
            if config_entry.disabled_by:
                if disabled_by is None:
                    disabled_by = DeviceEntryDisabler.CONFIG_ENTRY
            elif disabled_by == DeviceEntryDisabler.CONFIG_ENTRY:
                disabled_by = None
        else:
            disabled_by = disabled_by if disabled_by is not UNDEFINED else None
        return DeviceEntry(
            area_id=self.area_id,
            config_entry_id=config_entry.entry_id,
            config_subentry_id=config_subentry_id,
            # type ignores: likely https://github.com/python/mypy/issues/8625
            connections=self.connections & connections,  # type: ignore[arg-type]
            created_at=self.created_at,
            disabled_by=disabled_by,
            identifiers=self.identifiers & identifiers,  # type: ignore[arg-type]
            id=self.id,
            labels=self.labels,  # type: ignore[arg-type]
            name_by_user=self.name_by_user,
        )

    @under_cached_property
    def as_storage_fragment(self) -> json_fragment:
        """Return a json fragment for storage."""
        return json_fragment(
            json_bytes(
                {
                    "area_id": self.area_id,
                    # config_entries and config_entries_subentries are deprecated and
                    # kept for backwards compatibility, they can be removed from the
                    # storage representation in HA Core 2026.12
                    "config_entries": list(self.config_entries),
                    "config_entries_subentries": {
                        config_entry_id: list(subentries)
                        for config_entry_id, subentries in (
                            self.config_entries_subentries.items()
                        )
                    },
                    "config_entry_id": self.config_entry_id,
                    "config_subentry_id": self.config_subentry_id,
                    "connections": list(self.connections),
                    "created_at": self.created_at,
                    "disabled_by": self.disabled_by
                    if self.disabled_by is not UNDEFINED
                    else None,
                    "disabled_by_undefined": self.disabled_by is UNDEFINED,
                    "identifiers": list(self.identifiers),
                    "id": self.id,
                    "labels": list(self.labels),
                    "modified_at": self.modified_at,
                    "name_by_user": self.name_by_user,
                    "orphaned_timestamp": self.orphaned_timestamp,
                }
            )
        )


class DeviceRegistryStore(storage.Store[dict[str, list[dict[str, Any]]]]):
    """Store entity registry data."""

    @override
    async def _async_migrate_func(  # noqa: C901
        self,
        old_major_version: int,
        old_minor_version: int,
        old_data: dict[str, list[dict[str, Any]]],
    ) -> dict[str, Any]:
        """Migrate to the new version."""
        # Support for a future major version bump to 2 added in HA Core 2025.2.
        # Major versions 1 and 2 will be the same, except that version 2 will no
        # longer store a list of config_entries.
        if old_major_version < 3:
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
                    device["labels"] = []
            if old_minor_version < 6:
                # Introduced in 2024.7
                for device in old_data["devices"]:
                    device["primary_config_entry"] = None
            if old_minor_version < 7:
                # Introduced in 2024.8
                for device in old_data["devices"]:
                    device["model_id"] = None
            if old_minor_version < 8:
                # Introduced in 2024.8
                created_at = utc_from_timestamp(0).isoformat()
                for device in old_data["devices"]:
                    device["created_at"] = device["modified_at"] = created_at
                for device in old_data["deleted_devices"]:
                    device["created_at"] = device["modified_at"] = created_at
            if old_minor_version < 9:
                # Introduced in 2025.2
                for device in old_data["devices"]:
                    device["config_entries_subentries"] = {
                        config_entry_id: {None}
                        for config_entry_id in device["config_entries"]
                    }
                for device in old_data["deleted_devices"]:
                    device["config_entries_subentries"] = {
                        config_entry_id: {None}
                        for config_entry_id in device["config_entries"]
                    }
            if old_minor_version < 10:
                # Introduced in 2025.6
                for device in old_data["deleted_devices"]:
                    device["area_id"] = None
                    device["disabled_by"] = None
                    device["labels"] = []
                    device["name_by_user"] = None
            if old_minor_version < 11:
                # Normalization of stored CONNECTION_NETWORK_MAC, introduced in 2025.8
                for device in old_data["devices"]:
                    device["connections"] = _normalize_connections(
                        device["connections"]
                    )
                for device in old_data["deleted_devices"]:
                    device["connections"] = _normalize_connections(
                        device["connections"]
                    )
            if old_minor_version < 12:
                # Version 1.12 adds undefined flags to deleted devices, this is a bugfix
                # of version 1.10
                for device in old_data["deleted_devices"]:
                    device["disabled_by_undefined"] = old_minor_version < 10
            if old_minor_version < 13:
                # Version 1.13 restricts a device to a single config entry and subentry,
                # introduced in 2026.8. Composite devices which belonged to several
                # config entries (or several subentries of one entry) are split into one
                # device per (config entry, subentry). Each split device keeps a copy of
                # the identifiers and connections and a reference (composite_device_id) to the original
                # composite device id, so that actions targeting the old id still reach
                # all split devices. Entities are moved to the matching split device when
                # the registries are loaded.
                migrated_at = utcnow().isoformat()
                split_devices: list[dict[str, Any]] = []
                for device in old_data["devices"]:
                    pairs = [
                        (config_entry_id, subentry_id)
                        for config_entry_id, subentry_ids in device[
                            "config_entries_subentries"
                        ].items()
                        for subentry_id in subentry_ids
                    ]
                    if not pairs:
                        # Drop devices that have no config entry / subentry pairs
                        continue
                    if len(pairs) == 1:
                        config_entry_id, subentry_id = pairs[0]
                        device["config_entry_id"] = config_entry_id
                        device["config_subentry_id"] = subentry_id
                        device["composite_device_id"] = None
                        device["composite_primary_config_entry"] = None
                        device["split_at"] = None
                        device["has_composite_identifiers"] = False
                        split_devices.append(device)
                        continue
                    old_id = device["id"]
                    composite_primary = device.get("primary_config_entry")
                    for config_entry_id, subentry_id in pairs:
                        split = copy.deepcopy(device)
                        split["id"] = uuid_util.random_uuid_hex()
                        split["config_entry_id"] = config_entry_id
                        split["config_subentry_id"] = subentry_id
                        # Keep the deprecated multi-entry keys single so a downgrade
                        # sees a consistent single-entry device
                        split["config_entries"] = [config_entry_id]
                        split["config_entries_subentries"] = {
                            config_entry_id: [subentry_id]
                        }
                        split["primary_config_entry"] = config_entry_id
                        split["composite_device_id"] = old_id
                        split["composite_primary_config_entry"] = composite_primary
                        split["split_at"] = migrated_at
                        split["has_composite_identifiers"] = True
                        split_devices.append(split)
                old_data["devices"] = split_devices
                split_deleted_devices: list[dict[str, Any]] = []
                for device in old_data["deleted_devices"]:
                    pairs = [
                        (config_entry_id, subentry_id)
                        for config_entry_id, subentry_ids in device[
                            "config_entries_subentries"
                        ].items()
                        for subentry_id in subentry_ids
                    ]
                    if len(pairs) <= 1:
                        # Unlike active devices, config_entry_id=None is a valid
                        # (orphaned) state for a deleted device, so a deleted device with
                        # no config entries is kept rather than dropped.
                        config_entry_id, subentry_id = (
                            pairs[0] if pairs else (None, None)
                        )
                        device["config_entry_id"] = config_entry_id
                        device["config_subentry_id"] = subentry_id
                        split_deleted_devices.append(device)
                        continue
                    # A deleted device that belonged to several config entries or
                    # subentries is split like an active one - each split keeps a copy of
                    # the identifiers/connections - so every config entry can still
                    # restore its share when a matching device is re-registered.
                    for config_entry_id, subentry_id in pairs:
                        split = copy.deepcopy(device)
                        split["id"] = uuid_util.random_uuid_hex()
                        split["config_entry_id"] = config_entry_id
                        split["config_subentry_id"] = subentry_id
                        split["config_entries"] = [config_entry_id]
                        split["config_entries_subentries"] = {
                            config_entry_id: [subentry_id]
                        }
                        split_deleted_devices.append(split)
                old_data["deleted_devices"] = split_deleted_devices

        if old_major_version > 2:
            raise NotImplementedError
        return old_data


class DeviceRegistryItems[_EntryTypeT: (DeviceEntry, DeletedDeviceEntry)](
    BaseRegistryItems[_EntryTypeT]
):
    """Container for device registry items, maps device id -> entry.

    Maintains two additional indexes. An identifier or connection can be shared by
    several devices, each belonging to a different config entry, so each index maps a
    connection or identifier to the devices that have it, keyed by config entry id:
    - (connection_type, connection identifier) -> {config_entry_id: entry}
    - (DOMAIN, identifier) -> {config_entry_id: entry}
    """

    def __init__(self) -> None:
        """Initialize the container."""
        super().__init__()
        self._connections: dict[tuple[str, str], dict[str | None, _EntryTypeT]] = {}
        self._identifiers: dict[tuple[str, str], dict[str | None, _EntryTypeT]] = {}

    @override
    def _index_entry(self, key: str, entry: _EntryTypeT) -> None:
        """Index an entry."""
        config_entry_id = entry.config_entry_id
        for connection in entry.connections:
            self._connections.setdefault(connection, {})[config_entry_id] = entry
        for identifier in entry.identifiers:
            self._identifiers.setdefault(identifier, {})[config_entry_id] = entry

    @override
    def _unindex_entry(
        self, key: str, replacement_entry: _EntryTypeT | None = None
    ) -> None:
        """Unindex an entry."""
        old_entry = self.data[key]
        config_entry_id = old_entry.config_entry_id
        for connection in old_entry.connections:
            if connection in self._connections:
                del self._connections[connection][config_entry_id]
                if not self._connections[connection]:
                    del self._connections[connection]
        for identifier in old_entry.identifiers:
            if identifier in self._identifiers:
                del self._identifiers[identifier][config_entry_id]
                if not self._identifiers[identifier]:
                    del self._identifiers[identifier]

    def get_entry(
        self,
        identifiers: set[tuple[str, str]] | None = None,
        connections: set[tuple[str, str]] | None = None,
        *,
        config_entry_id: str | None | UndefinedType = UNDEFINED,
    ) -> _EntryTypeT | None:
        """Get the first entry matching identifiers or connections.

        If config_entry_id is given, only an entry belonging to that config entry is
        returned. Otherwise the first matching entry from any config entry is returned.
        """
        if identifiers:
            for identifier in identifiers:
                if (by_config_entry := self._identifiers.get(identifier)) is not None:
                    if config_entry_id is UNDEFINED:
                        return next(iter(by_config_entry.values()))
                    if config_entry_id in by_config_entry:
                        return by_config_entry[config_entry_id]
        if not connections:
            return None
        for connection in _normalize_connections(connections):
            if (by_config_entry := self._connections.get(connection)) is not None:
                if config_entry_id is UNDEFINED:
                    return next(iter(by_config_entry.values()))
                if config_entry_id in by_config_entry:
                    return by_config_entry[config_entry_id]
        return None

    def get_entries(
        self,
        identifiers: set[tuple[str, str]] | None = None,
        connections: set[tuple[str, str]] | None = None,
    ) -> list[_EntryTypeT]:
        """Get all entries matching identifiers or connections, across config entries."""
        entries: dict[str, _EntryTypeT] = {}
        if identifiers:
            for identifier in identifiers:
                if (by_config_entry := self._identifiers.get(identifier)) is not None:
                    for entry in by_config_entry.values():
                        entries[entry.id] = entry
        if connections:
            for connection in _normalize_connections(connections):
                if (by_config_entry := self._connections.get(connection)) is not None:
                    for entry in by_config_entry.values():
                        entries[entry.id] = entry
        return list(entries.values())


class ActiveDeviceRegistryItems(DeviceRegistryItems[DeviceEntry]):
    """Container for active (non-deleted) device registry entries."""

    def __init__(self) -> None:
        """Initialize the container.

        Maintains four additional indexes:

        - area_id -> dict[key, True]
        - config_entry_id -> dict[key, True]
        - label -> dict[key, True]
        - composite_device_id -> dict[key, True]
        """
        super().__init__()
        self._area_id_index: RegistryIndexType = defaultdict(dict)
        self._config_entry_id_index: RegistryIndexType = defaultdict(dict)
        self._labels_index: RegistryIndexType = defaultdict(dict)
        self._composite_device_id_index: RegistryIndexType = defaultdict(dict)

    @override
    def _index_entry(self, key: str, entry: DeviceEntry) -> None:
        """Index an entry."""
        super()._index_entry(key, entry)
        if (area_id := entry.area_id) is not None:
            self._area_id_index[area_id][key] = True
        for label in entry.labels:
            self._labels_index[label][key] = True
        self._config_entry_id_index[entry.config_entry_id][key] = True
        if entry.composite_device_id is not None:
            self._composite_device_id_index[entry.composite_device_id][key] = True

    @override
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
        self._unindex_entry_value(
            key, entry.config_entry_id, self._config_entry_id_index
        )
        if entry.composite_device_id is not None:
            self._unindex_entry_value(
                key, entry.composite_device_id, self._composite_device_id_index
            )
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

    def get_devices_for_composite_device_id(
        self, composite_device_id: str
    ) -> list[DeviceEntry]:
        """Get the devices a pre-migration composite device was split into."""
        data = self.data
        return [
            data[key]
            for key in self._composite_device_id_index.get(composite_device_id, ())
        ]


class DeviceRegistry(BaseRegistry[dict[str, list[dict[str, Any]]]]):
    """Class to hold a registry of devices."""

    devices: ActiveDeviceRegistryItems
    deleted_devices: DeviceRegistryItems[DeletedDeviceEntry]
    _device_data: dict[str, DeviceEntry]

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the device registry."""
        self.hass = hass
        self._loaded_event = asyncio.Event()
        self._store = DeviceRegistryStore(
            hass,
            STORAGE_VERSION_MAJOR,
            STORAGE_KEY,
            atomic_writes=True,
            minor_version=STORAGE_VERSION_MINOR,
            serialize_in_event_loop=False,
        )

    @callback
    def async_get(self, device_id: str) -> DeviceEntry | None:
        """Get device.

        We retrieve the DeviceEntry from the underlying dict to avoid
        the overhead of the UserDict __getitem__.

        For a pre-migration composite device id, a read-only composite device
        merged from the split devices is returned, so integration code that resolves a
        device by id (e.g. in a service handler) keeps working. The composite is
        synthesized on demand and never stored, so it stays invisible to enumeration,
        identifier search and the frontend device list.
        """
        if (device := self._device_data.get(device_id)) is not None:
            return device
        if split_devices := self.devices.get_devices_for_composite_device_id(device_id):
            return self._restore_composite_device(device_id, split_devices)
        return None

    @callback
    def _restore_composite_device(
        self, device_id: str, split_devices: list[DeviceEntry]
    ) -> DeviceEntry:
        """Synthesize a read-only composite device from its split devices."""
        composite_subentries: dict[str, set[str | None]] = {}
        identifiers: set[tuple[str, str]] = set()
        connections: set[tuple[str, str]] = set()
        for split_device in split_devices:
            composite_subentries.setdefault(split_device.config_entry_id, set()).add(
                split_device.config_subentry_id
            )
            identifiers |= split_device.identifiers
            connections |= split_device.connections
        # Functional identity (identifiers, connections, serial_number) is consistent
        # across splits of the same physical device. Use the split owning the composite's
        # former primary config entry as the base, so config_entry_id - and thus
        # primary_config_entry - reports the composite's former primary.
        primary_config_entry = split_devices[0].composite_primary_config_entry
        base = next(
            (
                split_device
                for split_device in split_devices
                if split_device.config_entry_id == primary_config_entry
            ),
            split_devices[0],
        )
        return attr.evolve(
            base,
            composite_subentries=composite_subentries,
            connections=connections,  # type: ignore[arg-type]
            id=device_id,
            identifiers=identifiers,  # type: ignore[arg-type]
        )

    @callback
    def async_get_device(
        self,
        identifiers: set[tuple[str, str]] | None = None,
        connections: set[tuple[str, str]] | None = None,
        *,
        config_entry_id: str | None | UndefinedType = UNDEFINED,
    ) -> DeviceEntry | None:
        """Check if a device is registered.

        Identifiers and connections are unique per config entry. If config_entry_id is
        passed, only the device owned by that config entry is returned. If it is not
        passed, the first matching device from any config entry is returned; since this
        is ambiguous when several config entries share an identifier or connection,
        callers are encouraged to always pass config_entry_id.
        """
        return self.devices.get_entry(
            identifiers, connections, config_entry_id=config_entry_id
        )

    @callback
    def async_get_devices(
        self,
        identifiers: set[tuple[str, str]] | None = None,
        connections: set[tuple[str, str]] | None = None,
    ) -> list[DeviceEntry]:
        """Return all devices matching identifiers or connections.

        Identifiers and connections are unique per config entry, so several devices
        (one per config entry) may share an identifier or connection.
        """
        return self.devices.get_entries(identifiers, connections)

    @callback
    def async_get_devices_for_composite_device_id(
        self, composite_device_id: str
    ) -> list[DeviceEntry]:
        """Return the devices a pre-migration composite device was split into.

        Composite devices which belonged to several config entries were split into one
        device per config entry during migration. The original composite device id is
        kept as composite_device_id on each split device so that actions targeting the
        old id still reach all split devices. Returns an empty list for a device id
        which is not a composite device id.
        """
        return self.devices.get_devices_for_composite_device_id(composite_device_id)

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
        config_subentry_id: str | None | UndefinedType = UNDEFINED,
        configuration_url: str | URL | None | UndefinedType = UNDEFINED,
        connections: set[tuple[str, str]] | None | UndefinedType = UNDEFINED,
        created_at: str | datetime | UndefinedType = UNDEFINED,  # will be ignored
        default_manufacturer: str | None | UndefinedType = UNDEFINED,
        default_model: str | None | UndefinedType = UNDEFINED,
        default_name: str | None | UndefinedType = UNDEFINED,
        # To disable a device if it gets created, does not affect existing devices
        disabled_by: DeviceEntryDisabler | None | UndefinedType = UNDEFINED,
        entry_type: DeviceEntryType | None | UndefinedType = UNDEFINED,
        hw_version: str | None | UndefinedType = UNDEFINED,
        identifiers: set[tuple[str, str]] | None | UndefinedType = UNDEFINED,
        manufacturer: str | None | UndefinedType = UNDEFINED,
        model: str | None | UndefinedType = UNDEFINED,
        model_id: str | None | UndefinedType = UNDEFINED,
        modified_at: str | datetime | UndefinedType = UNDEFINED,  # will be ignored
        name: str | None | UndefinedType = UNDEFINED,
        serial_number: str | None | UndefinedType = UNDEFINED,
        suggested_area: str | None | UndefinedType = UNDEFINED,
        sw_version: str | None | UndefinedType = UNDEFINED,
        translation_key: str | None = None,
        translation_placeholders: Mapping[str, str] | None = None,
        # via_device is deprecated and will be removed in HA Core 2027.8, use
        # via_device_id instead
        via_device: tuple[str, str] | None | UndefinedType = UNDEFINED,
        via_device_id: str | None | UndefinedType = UNDEFINED,
    ) -> DeviceEntry:
        """Get device. Create if it doesn't exist."""
        default_manufacturer = _validate_str(
            "default_manufacturer", default_manufacturer
        )
        default_model = _validate_str("default_model", default_model)
        validated_fields = _validate_device_info_fields(
            configuration_url=configuration_url,
            hw_version=hw_version,
            manufacturer=manufacturer,
            model=model,
            model_id=model_id,
            serial_number=serial_number,
            sw_version=sw_version,
        )

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
                ("connections", connections),
                ("default_manufacturer", default_manufacturer),
                ("default_model", default_model),
                ("default_name", default_name),
                ("entry_type", entry_type),
                ("identifiers", identifiers),
                ("name", name),
                ("suggested_area", suggested_area),
                ("via_device", via_device),
                ("via_device_id", via_device_id),
                *validated_fields.items(),
            )
            if val is not UNDEFINED
        }

        device_info_type = _determine_device_info_type(config_entry, device_info)

        if identifiers is None or identifiers is UNDEFINED:
            identifiers = set()

        if connections is None or connections is UNDEFINED:
            connections = set()
        else:
            connections = _normalize_connections(connections)

        device = self.devices.get_entry(
            connections=connections,
            identifiers=identifiers,
            config_entry_id=config_entry_id,
        )

        is_new = False

        if device is None:
            is_new = True

            deleted_device = self.deleted_devices.get_entry(
                connections=connections,
                identifiers=identifiers,
                config_entry_id=config_entry_id,
            )
            if deleted_device is None:
                area_id: str | None = None
                if (
                    suggested_area is not None
                    and suggested_area is not UNDEFINED
                    and suggested_area != ""
                ):
                    # Circular dep
                    from . import area_registry as ar  # noqa: PLC0415

                    area = ar.async_get(self.hass).async_get_or_create(suggested_area)
                    area_id = area.id
                device = DeviceEntry(
                    area_id=area_id,
                    config_entry_id=config_entry_id,
                    # Interpret not specifying a subentry as None
                    config_subentry_id=(
                        config_subentry_id
                        if config_subentry_id is not UNDEFINED
                        else None
                    ),
                )

            else:
                self.deleted_devices.pop(deleted_device.id)
                device = deleted_device.to_device_entry(
                    config_entry,
                    # Interpret not specifying a subentry as None
                    config_subentry_id if config_subentry_id is not UNDEFINED else None,
                    connections,
                    identifiers,
                    disabled_by,
                )
                disabled_by = UNDEFINED

            self.devices[device.id] = device
            # If creating a new device, default to the config entry name
            if device_info_type == "primary" and (not name or name is UNDEFINED):
                name = config_entry.title

        if default_manufacturer is not UNDEFINED and device.manufacturer is None:
            validated_fields["manufacturer"] = default_manufacturer

        if default_model is not UNDEFINED and device.model is None:
            validated_fields["model"] = default_model

        if default_name is not UNDEFINED and device.name is None:
            name = default_name

        if via_device is not None and via_device is not UNDEFINED:
            if via_device_id is not UNDEFINED:
                raise HomeAssistantError(
                    "Passing both `via_device` and `via_device_id` is not allowed; "
                    "`via_device` is deprecated, pass `via_device_id` only"
                )
            # Resolve the deprecated via_device to a device id. The identifier is not
            # scoped to a config entry, so this lookup is ambiguous, which is why
            # via_device is deprecated.
            if (via := self.devices.get_entry(identifiers={via_device})) is None:
                report_usage(
                    "calls `device_registry.async_get_or_create` referencing a "
                    f"non existing `via_device` {via_device}, "
                    f"with device info: {device_info}",
                    core_behavior=ReportBehavior.LOG,
                    breaks_in_ha_version="2025.12.0",
                )
            via_device_id = via.id if via else UNDEFINED

        # On the owning integration's first re-registration of a device created by
        # splitting a pre-migration composite device, replace the identifiers and
        # connections copied from the composite with the ones the integration provides,
        # instead of merging. This block and the has_composite_identifiers flag
        # can be removed in HA Core 2027.8.
        identifiers_connections: dict[str, Any]
        has_composite_identifiers: bool | UndefinedType = UNDEFINED
        if not is_new and device.has_composite_identifiers:
            identifiers_connections = {
                "new_connections": connections,
                "new_identifiers": identifiers,
            }
            has_composite_identifiers = False
        else:
            identifiers_connections = {
                "merge_connections": connections or UNDEFINED,
                "merge_identifiers": identifiers or UNDEFINED,
            }

        device = self._async_update_device(
            device.id,
            allow_collisions=True,
            disabled_by=disabled_by,
            entry_type=entry_type,
            is_new=is_new,
            name=name,
            has_composite_identifiers=has_composite_identifiers,
            # Move the device if the integration re-registers it under a different
            # subentry; UNDEFINED leaves the subentry unchanged. Also validates an
            # explicitly provided subentry for new devices.
            new_config_subentry_id=config_subentry_id,
            suggested_area=suggested_area,
            via_device_id=via_device_id,
            **identifiers_connections,
            **validated_fields,
        )

        # This is safe because _async_update_device will always return a device
        # in this use case.
        assert device
        return device

    @callback
    def _async_update_device(  # noqa: C901
        self,
        device_id: str,
        *,
        add_config_entry_id: str | UndefinedType = UNDEFINED,
        add_config_subentry_id: str | None | UndefinedType = UNDEFINED,
        # Temporary flag so we don't blow up when collisions are implicitly introduced
        # by calls to async_get_or_create.
        allow_collisions: bool = False,
        area_id: str | None | UndefinedType = UNDEFINED,
        configuration_url: str | URL | None | UndefinedType = UNDEFINED,
        disabled_by: DeviceEntryDisabler | None | UndefinedType = UNDEFINED,
        entry_type: DeviceEntryType | None | UndefinedType = UNDEFINED,
        hw_version: str | None | UndefinedType = UNDEFINED,
        is_new: bool = False,
        labels: set[str] | UndefinedType = UNDEFINED,
        manufacturer: str | None | UndefinedType = UNDEFINED,
        merge_connections: set[tuple[str, str]] | UndefinedType = UNDEFINED,
        merge_identifiers: set[tuple[str, str]] | UndefinedType = UNDEFINED,
        model: str | None | UndefinedType = UNDEFINED,
        model_id: str | None | UndefinedType = UNDEFINED,
        name_by_user: str | None | UndefinedType = UNDEFINED,
        name: str | None | UndefinedType = UNDEFINED,
        # has_composite_identifiers can be removed in HA Core 2027.8
        has_composite_identifiers: bool | UndefinedType = UNDEFINED,
        new_config_entry_id: str | UndefinedType = UNDEFINED,
        new_config_subentry_id: str | None | UndefinedType = UNDEFINED,
        new_connections: set[tuple[str, str]] | UndefinedType = UNDEFINED,
        new_identifiers: set[tuple[str, str]] | UndefinedType = UNDEFINED,
        remove_config_entry_id: str | UndefinedType = UNDEFINED,
        remove_config_subentry_id: str | None | UndefinedType = UNDEFINED,
        serial_number: str | None | UndefinedType = UNDEFINED,
        # Can be removed when suggested_area is removed from DeviceEntry
        suggested_area: str | None | UndefinedType = UNDEFINED,
        sw_version: str | None | UndefinedType = UNDEFINED,
        via_device_id: str | None | UndefinedType = UNDEFINED,
    ) -> DeviceEntry | None:
        """Private update device attributes.

        :param add_config_subentry_id: Add the device to a specific
            subentry of add_config_entry_id
        :param remove_config_subentry_id: Remove the device from a
            specific subentry of remove_config_entry_id
        """
        old = self.devices[device_id]

        new_values: dict[str, Any] = {}  # Dict with new key/value pairs
        old_values: dict[str, Any] = {}  # Dict with old key/value pairs

        if add_config_entry_id is not UNDEFINED:
            if (
                add_config_entry := self.hass.config_entries.async_get_entry(
                    add_config_entry_id
                )
            ) is None:
                raise HomeAssistantError(
                    f"Can't link device to unknown config entry {add_config_entry_id}"
                )

        if add_config_subentry_id is not UNDEFINED:
            if add_config_entry_id is UNDEFINED:
                raise HomeAssistantError(
                    "Can't add config subentry without specifying config entry"
                )
            if (
                add_config_subentry_id
                # mypy says add_config_entry can be None. That's impossible, because we
                # raise above if that happens
                and add_config_subentry_id not in add_config_entry.subentries  # type: ignore[union-attr]
            ):
                raise HomeAssistantError(
                    f"Config entry {add_config_entry_id} has no"
                    f" subentry {add_config_subentry_id}"
                )

        if (
            remove_config_subentry_id is not UNDEFINED
            and remove_config_entry_id is UNDEFINED
        ):
            raise HomeAssistantError(
                "Can't remove config subentry without specifying config entry"
            )

        if (
            new_config_entry_id is not UNDEFINED
            and self.hass.config_entries.async_get_entry(new_config_entry_id) is None
        ):
            raise HomeAssistantError(
                f"Can't move device to unknown config entry {new_config_entry_id}"
            )

        if (
            new_config_entry_id is not UNDEFINED
            or new_config_subentry_id is not UNDEFINED
        ) and (
            add_config_entry_id is not UNDEFINED
            or remove_config_entry_id is not UNDEFINED
        ):
            raise HomeAssistantError(
                "Can't combine new_config_entry_id or new_config_subentry_id with "
                "add_config_entry_id or remove_config_entry_id"
            )

        if not new_connections and not new_identifiers:
            raise HomeAssistantError(
                "A device must have at least one of identifiers or connections"
            )

        if merge_connections is not UNDEFINED and new_connections is not UNDEFINED:
            raise HomeAssistantError(
                "Cannot define both merge_connections and new_connections"
            )

        if merge_identifiers is not UNDEFINED and new_identifiers is not UNDEFINED:
            raise HomeAssistantError(
                "Cannot define both merge_identifiers and new_identifiers"
            )

        # A device belongs to exactly one config entry and subentry:
        # - add_config_entry_id (with an optional add_config_subentry_id) records a
        #   transient pending move to that config entry and subentry; on its own it does
        #   not move the device. Integrations move a device by adding the new config
        #   entry and then removing the current one, often in separate calls; the removal
        #   of the current config entry performs the pending move.
        # - remove_config_entry_id on the owning entry performs a pending move if there
        #   is one, otherwise it removes the device, since it has no other config entry.
        # - new_config_entry_id / new_config_subentry_id move the device immediately.
        target_config_entry_id: str | UndefinedType = UNDEFINED
        target_config_subentry_id: str | None | UndefinedType = UNDEFINED
        pending_move: tuple[str, str | None] | None | UndefinedType = UNDEFINED
        if new_config_entry_id is not UNDEFINED:
            target_config_entry_id = new_config_entry_id
            target_config_subentry_id = (
                new_config_subentry_id
                if new_config_subentry_id is not UNDEFINED
                else None
            )
        elif new_config_subentry_id is not UNDEFINED:
            target_config_subentry_id = new_config_subentry_id
        else:
            if add_config_entry_id is not UNDEFINED:
                pending_move = (
                    add_config_entry_id,
                    add_config_subentry_id
                    if add_config_subentry_id is not UNDEFINED
                    else None,
                )
            if remove_config_entry_id == old.config_entry_id and (
                remove_config_subentry_id is UNDEFINED
                or remove_config_subentry_id == old.config_subentry_id
            ):
                move_target = (
                    pending_move if pending_move is not UNDEFINED else old._pending_move  # noqa: SLF001
                )
                if move_target is None:
                    self.async_remove_device(device_id)
                    return None
                target_config_entry_id, target_config_subentry_id = move_target
                pending_move = None

        if target_config_subentry_id not in (UNDEFINED, None):
            resolved_config_entry_id = (
                target_config_entry_id
                if target_config_entry_id is not UNDEFINED
                else old.config_entry_id
            )
            resolved_config_entry = self.hass.config_entries.async_get_entry(
                resolved_config_entry_id
            )
            if (
                resolved_config_entry is None
                or target_config_subentry_id not in resolved_config_entry.subentries
            ):
                raise HomeAssistantError(
                    f"Config entry {resolved_config_entry_id} has no"
                    f" subentry {target_config_subentry_id}"
                )

        if (
            target_config_entry_id is not UNDEFINED
            and target_config_entry_id != old.config_entry_id
        ):
            new_values["config_entry_id"] = target_config_entry_id
            old_values["config_entry_id"] = old.config_entry_id
        if (
            target_config_subentry_id is not UNDEFINED
            and target_config_subentry_id != old.config_subentry_id
        ):
            new_values["config_subentry_id"] = target_config_subentry_id
            old_values["config_subentry_id"] = old.config_subentry_id
        # pending_move is a transient runtime-only attribute; it is not reported in the
        # update event (not added to old_values) and never stored
        if pending_move is not UNDEFINED and pending_move != old._pending_move:  # noqa: SLF001
            new_values["pending_move"] = pending_move

        # Identifiers and connections are unique per config entry, so when the device is
        # moved to another config entry they are validated against the new one
        effective_config_entry_id = (
            target_config_entry_id
            if target_config_entry_id is not UNDEFINED
            else old.config_entry_id
        )

        added_connections: set[tuple[str, str]] | None = None
        added_identifiers: set[tuple[str, str]] | None = None

        if merge_connections is not UNDEFINED:
            normalized_connections = self._validate_connections(
                device_id,
                effective_config_entry_id,
                merge_connections,
                allow_collisions,
            )
            old_connections = old.connections
            if not normalized_connections.issubset(old_connections):
                added_connections = normalized_connections
                new_values["connections"] = old_connections | normalized_connections
                old_values["connections"] = old_connections

        if merge_identifiers is not UNDEFINED:
            merge_identifiers = self._validate_identifiers(
                device_id,
                effective_config_entry_id,
                merge_identifiers,
                allow_collisions,
            )
            old_identifiers = old.identifiers
            if not merge_identifiers.issubset(old_identifiers):
                added_identifiers = merge_identifiers
                new_values["identifiers"] = old_identifiers | merge_identifiers
                old_values["identifiers"] = old_identifiers

        if new_connections is not UNDEFINED:
            added_connections = new_values["connections"] = self._validate_connections(
                device_id, effective_config_entry_id, new_connections, False
            )
            old_values["connections"] = old.connections

        if new_identifiers is not UNDEFINED:
            added_identifiers = new_values["identifiers"] = self._validate_identifiers(
                device_id, effective_config_entry_id, new_identifiers, False
            )
            old_values["identifiers"] = old.identifiers

        for attr_name, value in (
            ("area_id", area_id),
            ("configuration_url", configuration_url),
            ("disabled_by", disabled_by),
            ("entry_type", entry_type),
            ("hw_version", hw_version),
            ("labels", labels),
            ("manufacturer", manufacturer),
            ("model", model),
            ("model_id", model_id),
            ("name", name),
            ("name_by_user", name_by_user),
            ("has_composite_identifiers", has_composite_identifiers),
            ("serial_number", serial_number),
            ("sw_version", sw_version),
            ("via_device_id", via_device_id),
        ):
            if value is not UNDEFINED and value != getattr(old, attr_name):
                new_values[attr_name] = value
                old_values[attr_name] = getattr(old, attr_name)

        # Can be removed when suggested_area is removed from DeviceEntry
        if suggested_area is not UNDEFINED and suggested_area != old._suggested_area:  # noqa: SLF001
            new_values["suggested_area"] = suggested_area
            old_values["suggested_area"] = old._suggested_area  # noqa: SLF001

        if not new_values and not is_new:
            return old

        # This condition can be removed when suggested_area is removed from DeviceEntry
        if not RUNTIME_ONLY_ATTRS.issuperset(new_values):
            # Change modified_at if we are changing something that we store
            new_values["modified_at"] = utcnow()

        self.hass.verify_event_loop_thread("device_registry._async_update_device")
        new = attr.evolve(old, **new_values)
        self.devices[device_id] = new

        # NOTE: Once we solve the broader issue of duplicated devices, we might
        # want to revisit it. Instead of simply removing the duplicated deleted device,
        # we might want to merge the information from it into the non-deleted device.
        for deleted_device in self.deleted_devices.get_entries(
            added_identifiers, added_connections
        ):
            if deleted_device.id in self.deleted_devices:
                del self.deleted_devices[deleted_device.id]

        # If its only run time attributes (suggested_area)
        # that do not get saved we do not want to write
        # to disk or fire an event as we would end up
        # firing events for data we have nothing to compare
        # against since its never saved on disk
        if RUNTIME_ONLY_ATTRS.issuperset(new_values):
            # This can be removed when suggested_area is removed from DeviceEntry
            return new

        self.async_schedule_save()

        data: EventDeviceRegistryUpdatedData
        if is_new:
            data = {"action": "create", "device_id": new.id}
        else:
            data = {"action": "update", "device_id": new.id, "changes": old_values}

        self.hass.bus.async_fire_internal(EVENT_DEVICE_REGISTRY_UPDATED, data)

        return new

    @callback
    def async_update_device(
        self,
        device_id: str,
        *,
        add_config_entry_id: str | UndefinedType = UNDEFINED,
        add_config_subentry_id: str | None | UndefinedType = UNDEFINED,
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
        model_id: str | None | UndefinedType = UNDEFINED,
        name_by_user: str | None | UndefinedType = UNDEFINED,
        name: str | None | UndefinedType = UNDEFINED,
        new_config_entry_id: str | UndefinedType = UNDEFINED,
        new_config_subentry_id: str | None | UndefinedType = UNDEFINED,
        new_connections: set[tuple[str, str]] | UndefinedType = UNDEFINED,
        new_identifiers: set[tuple[str, str]] | UndefinedType = UNDEFINED,
        remove_config_entry_id: str | UndefinedType = UNDEFINED,
        remove_config_subentry_id: str | None | UndefinedType = UNDEFINED,
        serial_number: str | None | UndefinedType = UNDEFINED,
        # suggested_area is deprecated and will be removed in 2026.9
        suggested_area: str | None | UndefinedType = UNDEFINED,
        sw_version: str | None | UndefinedType = UNDEFINED,
        via_device_id: str | None | UndefinedType = UNDEFINED,
    ) -> DeviceEntry | None:
        """Update device attributes.

        A device belongs to a single config entry and subentry. To move a device to
        another config entry or subentry, pass new_config_entry_id and/or
        new_config_subentry_id. To remove a device, pass remove_config_entry_id with the
        device's config entry.

        :param add_config_entry_id: Deprecated. Combined with remove_config_entry_id it
            moves the device; on its own it does nothing.
        :param add_config_subentry_id: Deprecated. Combined with remove_config_subentry_id
            it moves the device to another subentry; on its own it does nothing.
        :param new_config_entry_id: Move the device to this config entry.
        :param new_config_subentry_id: Move the device to this subentry.
        :param remove_config_entry_id: Remove the device if it is the device's config
            entry, unless combined with add_config_entry_id to move the device.
        :param remove_config_subentry_id: Remove the device from a specific subentry of
            remove_config_entry_id.
        """
        if suggested_area is not UNDEFINED:
            report_usage(
                "passes a suggested_area to device_registry.async_update device",
                core_behavior=ReportBehavior.LOG,
                breaks_in_ha_version="2026.9.0",
            )

        validated_fields = _validate_device_info_fields(
            configuration_url=configuration_url,
            hw_version=hw_version,
            manufacturer=manufacturer,
            model=model,
            model_id=model_id,
            serial_number=serial_number,
            sw_version=sw_version,
        )

        return self._async_update_device(
            device_id,
            add_config_entry_id=add_config_entry_id,
            add_config_subentry_id=add_config_subentry_id,
            area_id=area_id,
            disabled_by=disabled_by,
            entry_type=entry_type,
            labels=labels,
            merge_connections=merge_connections,
            merge_identifiers=merge_identifiers,
            name_by_user=name_by_user,
            name=name,
            new_config_entry_id=new_config_entry_id,
            new_config_subentry_id=new_config_subentry_id,
            new_connections=new_connections,
            new_identifiers=new_identifiers,
            remove_config_entry_id=remove_config_entry_id,
            remove_config_subentry_id=remove_config_subentry_id,
            suggested_area=suggested_area,
            via_device_id=via_device_id,
            **validated_fields,
        )

    @callback
    def _validate_connections(
        self,
        device_id: str,
        config_entry_id: str,
        connections: set[tuple[str, str]],
        allow_collisions: bool,
    ) -> set[tuple[str, str]]:
        """Normalize and validate connections, raise on collision with other devices.

        Connections are unique per config entry, so only collisions with other devices
        of the same config entry are considered.
        """
        normalized_connections = _normalize_connections(connections)
        if allow_collisions:
            return normalized_connections

        for connection in normalized_connections:
            # We need to iterate over each connection because if there is a
            # conflict, the index will only see the last one and we will not
            # be able to tell which one caused the conflict
            if (
                existing_device := self.devices.get_entry(
                    connections={connection}, config_entry_id=config_entry_id
                )
            ) and existing_device.id != device_id:
                raise DeviceConnectionCollisionError(
                    normalized_connections, existing_device
                )

        return normalized_connections

    @callback
    def _validate_identifiers(
        self,
        device_id: str,
        config_entry_id: str,
        identifiers: set[tuple[str, str]],
        allow_collisions: bool,
    ) -> set[tuple[str, str]]:
        """Validate identifiers, raise on collision with other devices.

        Identifiers are unique per config entry, so only collisions with other devices
        of the same config entry are considered.
        """
        if allow_collisions:
            return identifiers

        for identifier in identifiers:
            # We need to iterate over each identifier because if there is a
            # conflict, the index will only see the last one and we will not
            # be able to tell which one caused the conflict
            if (
                existing_device := self.devices.get_entry(
                    identifiers={identifier}, config_entry_id=config_entry_id
                )
            ) and existing_device.id != device_id:
                raise DeviceIdentifierCollisionError(identifiers, existing_device)

        return identifiers

    @callback
    def async_remove_device(self, device_id: str) -> None:
        """Remove a device from the device registry."""
        self.hass.verify_event_loop_thread("device_registry.async_remove_device")
        device = self.devices.pop(device_id)
        self.deleted_devices[device_id] = DeletedDeviceEntry(
            area_id=device.area_id,
            config_entry_id=device.config_entry_id,
            config_subentry_id=device.config_subentry_id,
            connections=device.connections,
            created_at=device.created_at,
            disabled_by=device.disabled_by,
            identifiers=device.identifiers,
            id=device.id,
            labels=device.labels,
            modified_at=utcnow(),
            name_by_user=device.name_by_user,
            orphaned_timestamp=None,
        )
        for other_device in list(self.devices.values()):
            if other_device.via_device_id == device_id:
                self._async_update_device(other_device.id, via_device_id=None)
        self.hass.bus.async_fire_internal(
            EVENT_DEVICE_REGISTRY_UPDATED,
            _EventDeviceRegistryUpdatedData_Remove(
                action="remove", device_id=device_id, device=device.dict_repr
            ),
        )
        self.async_schedule_save()

    @override
    async def _async_load(self) -> None:
        """Load the device registry."""
        if self._loaded_event.is_set():
            raise RuntimeError("Device registry is already loaded")

        async_setup_cleanup(self.hass, self)

        data = await self._store.async_load()

        devices = ActiveDeviceRegistryItems()
        deleted_devices: DeviceRegistryItems[DeletedDeviceEntry] = DeviceRegistryItems()

        if data is not None:
            for device in data["devices"]:
                devices[device["id"]] = DeviceEntry(
                    area_id=device["area_id"],
                    config_entry_id=device["config_entry_id"],
                    config_subentry_id=device["config_subentry_id"],
                    configuration_url=device["configuration_url"],
                    # type ignores (if tuple arg was cast): likely https://github.com/python/mypy/issues/8625
                    connections={
                        tuple(conn)  # type: ignore[misc]
                        for conn in device["connections"]
                    },
                    created_at=datetime.fromisoformat(device["created_at"]),
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
                    composite_device_id=device["composite_device_id"],
                    composite_primary_config_entry=device[
                        "composite_primary_config_entry"
                    ],
                    split_at=(
                        datetime.fromisoformat(device["split_at"])
                        if device["split_at"]
                        else None
                    ),
                    manufacturer=device["manufacturer"],
                    model=device["model"],
                    model_id=device["model_id"],
                    modified_at=datetime.fromisoformat(device["modified_at"]),
                    name_by_user=device["name_by_user"],
                    name=device["name"],
                    has_composite_identifiers=device["has_composite_identifiers"],
                    serial_number=device["serial_number"],
                    sw_version=device["sw_version"],
                    via_device_id=device["via_device_id"],
                )

            # Introduced in 0.111
            def get_optional_enum[_EnumT: StrEnum](
                cls: type[_EnumT], value: str | None, undefined: bool
            ) -> _EnumT | UndefinedType | None:
                """Convert string to the passed enum, UNDEFINED or None."""
                if undefined:
                    return UNDEFINED
                if value is None:
                    return None
                try:
                    return cls(value)
                except ValueError:
                    return None

            for device in data["deleted_devices"]:
                deleted_devices[device["id"]] = DeletedDeviceEntry(
                    area_id=device["area_id"],
                    config_entry_id=device["config_entry_id"],
                    config_subentry_id=device["config_subentry_id"],
                    connections={tuple(conn) for conn in device["connections"]},
                    created_at=datetime.fromisoformat(device["created_at"]),
                    disabled_by=get_optional_enum(
                        DeviceEntryDisabler,
                        device["disabled_by"],
                        device["disabled_by_undefined"],
                    ),
                    identifiers={tuple(iden) for iden in device["identifiers"]},
                    id=device["id"],
                    labels=set(device["labels"]),
                    modified_at=datetime.fromisoformat(device["modified_at"]),
                    name_by_user=device["name_by_user"],
                    orphaned_timestamp=device["orphaned_timestamp"],
                )

        self.devices = devices
        self.deleted_devices = deleted_devices
        self._device_data = devices.data

        self._loaded_event.set()

    async def async_wait_loaded(self) -> None:
        """Wait until the device registry is fully loaded."""
        await self._loaded_event.wait()

    @callback
    @override
    def _data_to_save(self) -> dict[str, Any]:
        """Return data of device registry to store in a file."""
        # Create intermediate lists to allow this method to be called from a thread
        # other than the event loop.
        return {
            "devices": [
                entry.as_storage_fragment for entry in list(self.devices.values())
            ],
            "deleted_devices": [
                entry.as_storage_fragment
                for entry in list(self.deleted_devices.values())
            ],
        }

    @callback
    def async_clear_config_entry(self, config_entry_id: str) -> None:
        """Clear config entry from registry entries."""
        now_time = time.time()
        for device in self.devices.get_devices_for_config_entry_id(config_entry_id):
            self._async_update_device(device.id, remove_config_entry_id=config_entry_id)
        # A split device records the composite's former primary config entry; when that
        # config entry is removed, clear the now-dangling reference so a restored
        # composite no longer points at a config entry that no longer exists
        for device in list(self.devices.values()):
            if device.composite_primary_config_entry == config_entry_id:
                self.devices[device.id] = attr.evolve(
                    device, composite_primary_config_entry=None
                )
                self.async_schedule_save()
        for deleted_device in list(self.deleted_devices.values()):
            if deleted_device.config_entry_id != config_entry_id:
                continue
            # The deleted device's owning config entry is being removed, mark it as
            # orphaned by clearing its config entry and adding a timestamp
            self.deleted_devices[deleted_device.id] = attr.evolve(
                deleted_device,
                config_entry_id=None,
                config_subentry_id=None,
                orphaned_timestamp=now_time,
            )
            self.async_schedule_save()

    @callback
    def async_clear_config_subentry(
        self, config_entry_id: str, config_subentry_id: str
    ) -> None:
        """Clear config subentry from registry entries."""
        now_time = time.time()
        for device in self.devices.get_devices_for_config_entry_id(config_entry_id):
            self._async_update_device(
                device.id,
                remove_config_entry_id=config_entry_id,
                remove_config_subentry_id=config_subentry_id,
            )
        for deleted_device in list(self.deleted_devices.values()):
            if (
                deleted_device.config_entry_id != config_entry_id
                or deleted_device.config_subentry_id != config_subentry_id
            ):
                continue
            # The deleted device's owning config subentry is being removed, mark it as
            # orphaned by clearing its config entry and adding a timestamp
            self.deleted_devices[deleted_device.id] = attr.evolve(
                deleted_device,
                config_entry_id=None,
                config_subentry_id=None,
                orphaned_timestamp=now_time,
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
            self._async_update_device(device.id, area_id=None)
        for deleted_device in list(self.deleted_devices.values()):
            if deleted_device.area_id != area_id:
                continue
            self.deleted_devices[deleted_device.id] = attr.evolve(
                deleted_device, area_id=None
            )
            self.async_schedule_save()

    @callback
    def async_clear_label_id(self, label_id: str) -> None:
        """Clear label from registry entries."""
        for device in self.devices.get_devices_for_label(label_id):
            self._async_update_device(device.id, labels=device.labels - {label_id})
        for deleted_device in list(self.deleted_devices.values()):
            if label_id not in deleted_device.labels:
                continue
            self.deleted_devices[deleted_device.id] = attr.evolve(
                deleted_device, labels=deleted_device.labels - {label_id}
            )
            self.async_schedule_save()


@callback
def async_get(hass: HomeAssistant) -> DeviceRegistry:
    """Get device registry."""
    try:
        return hass.data[DATA_REGISTRY]
    except KeyError as ex:
        raise RuntimeError("Device registry not set up") from ex


def async_setup(hass: HomeAssistant) -> None:
    """Set up device registry."""
    if DATA_REGISTRY in hass.data:
        raise RuntimeError("Device registry is already set up")
    hass.data[DATA_REGISTRY] = DeviceRegistry(hass)


async def async_load(hass: HomeAssistant, *, load_empty: bool = False) -> None:
    """Load device registry."""
    await async_get(hass).async_load(load_empty=load_empty)


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
    """

    devices = async_entries_for_config_entry(registry, config_entry.entry_id)

    if not config_entry.disabled_by:
        for device in devices:
            if device.disabled_by is not DeviceEntryDisabler.CONFIG_ENTRY:
                continue
            registry._async_update_device(device.id, disabled_by=None)  # noqa: SLF001
        return

    for device in devices:
        if device.disabled:
            # Device already disabled, do not overwrite
            continue
        registry._async_update_device(  # noqa: SLF001
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
        if device.config_entry_id in config_entry_ids
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
        if device.config_entry_id not in config_entry_ids:
            dev_reg._async_update_device(  # noqa: SLF001
                device.id, remove_config_entry_id=device.config_entry_id
            )

    # Periodic purge of orphaned devices to avoid the registry
    # growing without bounds when there are lots of deleted devices
    dev_reg.async_purge_expired_orphaned_devices()


@callback
def async_setup_cleanup(hass: HomeAssistant, dev_reg: DeviceRegistry) -> None:
    """Clean up device registry when entities removed."""
    from . import entity_registry, label_registry as lr  # noqa: PLC0415

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
