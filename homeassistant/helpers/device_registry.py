"""Provide a way to connect entities belonging to one device."""

import asyncio
from collections import defaultdict
from collections.abc import Collection, Iterable, Iterator, Mapping, Set as AbstractSet
import copy
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from functools import lru_cache
import logging
import os
import shutil
import time
from typing import (
    TYPE_CHECKING,
    Any,
    Literal,
    NamedTuple,
    Required,
    TypedDict,
    Unpack,
    overload,
    override,
)

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
from .frame import (
    MissingIntegrationFrame,
    ReportBehavior,
    get_integration_frame,
    report_usage,
)
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
STORAGE_VERSION_MAJOR = 3
STORAGE_VERSION_MINOR = 4

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


@dataclass(frozen=True, slots=True)
class _PendingMove:
    """A deferred config-entry move recorded by add_config_entry_id.

    A later remove_config_entry_id from the same integration (origin_domain) completes
    the move; one from a different integration cancels it. Runtime-only, never stored.
    """

    config_entry_id: str
    config_subentry_id: str | None
    origin_domain: str | None


def _current_integration_domain() -> str | None:
    """Return the domain of the integration in the current call stack, if any."""
    try:
        return get_integration_frame().integration
    except MissingIntegrationFrame:
        return None


CONFIGURATION_URL_SCHEMES = {"http", "https", "homeassistant"}


class DeviceEntryDisabler(StrEnum):
    """What disabled a device entry."""

    CONFIG_ENTRY = "config_entry"
    # A child device disabled because its parent device is disabled.
    DEVICE = "device"
    INTEGRATION = "integration"
    USER = "user"


class DeviceInfo(TypedDict, total=False):
    """Entity device information for device registry."""

    configuration_url: str | URL | None
    connections: set[tuple[str, str]]
    entry_type: DeviceEntryType | None
    identifiers: set[tuple[str, str]]
    manufacturer: str | None
    model: str | None
    model_id: str | None
    name: str | None
    serial_number: str | None
    suggested_area: str | None
    sw_version: str | None
    hw_version: str | None
    translation_key: str | None
    translation_placeholders: Mapping[str, str] | None
    via_device_id: str


class ChildDeviceInfo(TypedDict, total=False):
    """Entity device information for a child device in the device registry.

    A child device is a lightweight logical part of a parent device. The parent
    is referenced by its device id, must already be registered by the same config
    entry, and must belong to the same config subentry.
    """

    identifiers: Required[set[tuple[str, str]]]
    name: str | None
    parent_device_id: Required[str]
    suggested_area: str | None
    translation_key: str | None
    translation_placeholders: Mapping[str, str] | None


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
        self, identifiers: set[tuple[str, str]], existing_device: AnyDeviceEntry
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


def _validate_device_info(
    config_entry: ConfigEntry,
    device_info: DeviceInfo,
) -> None:
    """Validate that a device info has enough information to match up a device."""
    if not device_info.get("connections") and not device_info.get("identifiers"):
        raise DeviceInfoError(
            config_entry.domain,
            device_info,
            "device info must include at least one of identifiers or connections",
        )
    for field in ("manufacturer", "model", "name"):
        if field in device_info and f"default_{field}" in device_info:
            raise DeviceInfoError(
                config_entry.domain,
                device_info,
                f"passing both `{field}` and `default_{field}` is not allowed",
            )


# Deprecated `async_get_or_create` parameters, mapped to the HA Core version they are
# removed in and the replacement parameter, or `None` if the parameter is ignored and
# has no replacement.
_DEPRECATED_DEVICE_INFO_PARAMETERS: dict[str, tuple[str, str | None]] = {
    "created_at": ("2027.9.0", None),
    "default_manufacturer": ("2027.9.0", "manufacturer"),
    "default_model": ("2027.9.0", "model"),
    "default_name": ("2027.9.0", "name"),
    "modified_at": ("2027.9.0", None),
    "via_device": ("2027.8.0", "via_device_id"),
}


class _ValidatedDeviceInfoFields(TypedDict):
    """Device info fields validated on create and update."""

    configuration_url: str | URL | UndefinedType | None
    hw_version: str | UndefinedType | None
    manufacturer: str | UndefinedType | None
    model: str | UndefinedType | None
    model_id: str | UndefinedType | None
    serial_number: str | UndefinedType | None
    sw_version: str | UndefinedType | None


_cached_parse_url = lru_cache(maxsize=512)(URL)
"""Parse a URL and cache the result."""


def _validate_str(name: str, value: Any) -> str | UndefinedType | None:
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
class BaseDeviceEntry:
    """Base class for device registry entries."""

    config_entry_id: str = attr.ib()

    area_id: str | None = attr.ib(default=None)
    config_subentry_id: str | None = attr.ib(default=None)
    created_at: datetime = attr.ib(factory=utcnow)
    disabled_by: DeviceEntryDisabler | None = attr.ib(default=None)
    id: str = attr.ib(factory=uuid_util.random_uuid_hex)
    identifiers: set[tuple[str, str]] = attr.ib(converter=set, factory=set)
    labels: set[str] = attr.ib(converter=set, factory=set)
    modified_at: datetime = attr.ib(factory=utcnow)
    name_by_user: str | None = attr.ib(default=None)
    name: str | None = attr.ib(default=None)
    _cache: dict[str, Any] = attr.ib(factory=dict, eq=False, init=False)

    @property
    def config_entries(self) -> set[str]:
        """Return the config entries this device belongs to.

        Deprecated compatibility shim: a device now belongs to a single config
        entry, available as config_entry_id.
        """
        return {self.config_entry_id}

    @property
    def config_entries_subentries(self) -> dict[str, set[str | None]]:
        """Return the config subentries this device belongs to.

        Deprecated compatibility shim: a device now belongs to a single config
        entry and subentry, available as config_entry_id and config_subentry_id.
        """
        return {self.config_entry_id: {self.config_subentry_id}}

    @property
    def primary_config_entry(self) -> str:
        """Return the primary config entry of this device.

        Deprecated compatibility shim: a device now belongs to a single config
        entry, available as config_entry_id, which is its primary config entry.
        """
        return self.config_entry_id

    @property
    def disabled(self) -> bool:
        """Return if entry is disabled."""
        return self.disabled_by is not None

    @property
    def dict_repr(self) -> dict[str, Any]:
        """Return a dict representation of the entry."""
        raise NotImplementedError

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


@attr.s(frozen=True, slots=True)
class DeviceEntry(BaseDeviceEntry):
    """Device Registry Entry."""

    configuration_url: str | None = attr.ib(default=None)
    connections: set[tuple[str, str]] = attr.ib(
        converter=set, factory=set, validator=_normalize_connections_validator
    )
    entry_type: DeviceEntryType | None = attr.ib(default=None)
    hw_version: str | None = attr.ib(default=None)
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
    # Set on devices created by splitting a pre-migration composite device: the
    # identifiers and connections copied from the composite have not yet been reconciled.
    # On the owning integration's first re-registration they are replaced with the ones
    # it provides and this flag is cleared - a one-shot marker, unlike composite_device_id
    # which is kept for the device's lifetime so old ids keep resolving; neither can be
    # derived from the other. This flag and the replacement logic can be removed in HA
    # Core 2027.8.
    has_composite_identifiers: bool = attr.ib(default=False)
    serial_number: str | None = attr.ib(default=None)
    # Suggested area is deprecated and will be removed from DeviceEntry in HA Core 2026.9.
    _suggested_area: str | None = attr.ib(default=None)
    sw_version: str | None = attr.ib(default=None)
    via_device_id: str | None = attr.ib(default=None)
    # Transient pending move target (config_entry_id, config_subentry_id) initiated by
    # add_config_entry_id and completed by a subsequent remove_config_entry_id. It is
    # never stored and is not part of equality. Can be removed in HA Core 2027.8.
    _pending_move: _PendingMove | None = attr.ib(default=None, eq=False)
    # Set only on the read-only composite device that async_get synthesizes on demand
    # for a pre-migration composite device id. It holds the union of the split
    # devices' config entries and subentries so callers see the pre-split device. It is
    # never stored and the composite is never added to the registry. Can be removed in
    # HA Core 2027.8.
    _composite_subentries: dict[str, set[str | None]] | None = attr.ib(
        default=None, eq=False
    )

    @property
    @override
    def config_entries(self) -> set[str]:
        """Return the config entries this device belongs to.

        Deprecated compatibility shim: a device now belongs to a single config
        entry, available as config_entry_id.
        """
        if self._composite_subentries is not None:
            return set(self._composite_subentries)
        return {self.config_entry_id}

    @property
    @override
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
    @override
    def dict_repr(self) -> dict[str, Any]:
        """Return a dict representation of the entry."""
        # Convert sets and tuples to lists
        # so the JSON serializer does not have to do
        # it every time
        return {
            "area_id": self.area_id,
            "configuration_url": self.configuration_url,
            # config_entries and config_entries_subentries are deprecated and kept for
            # backwards compatibility, they can be removed in HA Core 2027.8. They use the
            # compatibility properties so a restored composite reports its merged entries.
            "config_entries": list(self.config_entries),
            "config_entries_subentries": {
                entry_id: list(subentries)
                for entry_id, subentries in self.config_entries_subentries.items()
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
            "parent_device_id": None,
            "primary_config_entry": self.primary_config_entry,
            "serial_number": self.serial_number,
            "sw_version": self.sw_version,
            "via_device_id": self.via_device_id,
        }

    @under_cached_property
    def as_storage_fragment(self) -> json_fragment:
        """Return a json fragment for storage."""
        return json_fragment(
            json_bytes(
                {
                    "area_id": self.area_id,
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


_CHILD_DEVICE_COMPAT_ATTRS = frozenset(
    {
        "configuration_url",
        "connections",
        "entry_type",
        "hw_version",
        "manufacturer",
        "model",
        "model_id",
        "serial_number",
        # "suggested_area",  # Excluded, to be removed in 2026.9
        "sw_version",
        "via_device_id",
    }
)


@attr.s(frozen=True, slots=True)
class ChildDeviceEntry(BaseDeviceEntry):
    """Child Device Registry Entry."""

    parent_device_id: str = attr.ib(kw_only=True)

    if not TYPE_CHECKING:
        # Hidden from the type checker, otherwise mypy disables [attr-defined]
        # errors when it sees the __getattr__ below.
        def __getattr__(self, name: str) -> Any:
            """Return the DeviceEntry default for a DeviceEntry-only attribute.

            Backwards-compatibility shim for custom integrations that access an
            attribute which only exists on DeviceEntry (e.g. connections,
            manufacturer): they get the DeviceEntry default and a deprecation warning.
            """
            if name not in _CHILD_DEVICE_COMPAT_ATTRS:
                raise AttributeError(
                    f"'{type(self).__name__}' object has no attribute '{name}'"
                )
            try:
                integration_frame = get_integration_frame()
            except MissingIntegrationFrame:
                integration_frame = None
            if integration_frame is None or not integration_frame.custom_integration:
                raise AttributeError(
                    f"'{type(self).__name__}' object has no attribute '{name}'"
                )
            report_usage(
                f"accesses ChildDeviceEntry.{name}, which does not exist on child "
                "devices",
                breaks_in_ha_version="2027.9.0",
                core_behavior=ReportBehavior.IGNORE,
                core_integration_behavior=ReportBehavior.IGNORE,
                custom_integration_behavior=ReportBehavior.LOG,
            )
            return set() if name == "connections" else None

    @property
    @override
    def dict_repr(self) -> dict[str, Any]:
        """Return a dict representation of the entry."""
        # Convert sets to lists so the JSON serializer does not have to each time.
        return {
            "area_id": self.area_id,
            "config_entry_id": self.config_entry_id,
            "config_subentry_id": self.config_subentry_id,
            "created_at": self.created_at.timestamp(),
            "disabled_by": self.disabled_by,
            "id": self.id,
            "identifiers": list(self.identifiers),
            "labels": list(self.labels),
            "modified_at": self.modified_at.timestamp(),
            "name_by_user": self.name_by_user,
            "name": self.name,
            "parent_device_id": self.parent_device_id,
        }

    @under_cached_property
    def as_storage_fragment(self) -> json_fragment:
        """Return a json fragment for storage."""
        return json_fragment(
            json_bytes(
                {
                    "area_id": self.area_id,
                    "config_entry_id": self.config_entry_id,
                    "config_subentry_id": self.config_subentry_id,
                    "created_at": self.created_at,
                    "disabled_by": self.disabled_by,
                    "id": self.id,
                    "identifiers": list(self.identifiers),
                    "labels": list(self.labels),
                    "modified_at": self.modified_at,
                    "name_by_user": self.name_by_user,
                    "name": self.name,
                    "parent_device_id": self.parent_device_id,
                }
            )
        )


type AnyDeviceEntry = DeviceEntry | ChildDeviceEntry


# async_update_device arguments that redefine which identifiers/connections a device is
# keyed by, or move it to another config entry. They are ambiguous on a synthesized
# composite (there is no single underlying device to retarget), so the composite shim
# drops them with a warning instead of fanning them out. serial_number is intentionally
# NOT here: it describes the physical device and is consistent across a composite's
# splits, so it fans out like sw_version. Can be removed in HA Core 2027.8.
_COMPOSITE_IGNORED_UPDATE_ARGS = (
    "merge_connections",
    "merge_identifiers",
    "new_config_entry_id",
    "new_config_subentry_id",
    "new_connections",
    "new_identifiers",
)


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
    # Domain of the config entry that owns (or owned) this device, recorded when the
    # device is deleted so a re-added config entry only restores an orphan from the same
    # integration. None for legacy stores.
    domain: str | None = attr.ib(default=None)
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

    def _calculate_disable_by(
        self,
        config_entry: ConfigEntry,
        disabled_by: DeviceEntryDisabler | UndefinedType | None,
    ) -> DeviceEntryDisabler | None:
        """Calculate disabled_by when restoring a deleted device."""
        if self.disabled_by is UNDEFINED:
            return disabled_by if disabled_by is not UNDEFINED else None
        disabled_by = self.disabled_by
        if disabled_by == DeviceEntryDisabler.DEVICE:
            # self.disabled_by is DEVICE only for a former child device, clear it
            # (to_child_device_entry re-derives it from the new parent device).
            disabled_by = None
        if config_entry.disabled_by:
            if disabled_by is None:
                disabled_by = DeviceEntryDisabler.CONFIG_ENTRY
        elif disabled_by == DeviceEntryDisabler.CONFIG_ENTRY:
            disabled_by = None
        return disabled_by

    def to_device_entry(
        self,
        config_entry: ConfigEntry,
        config_subentry_id: str | None,
        connections: set[tuple[str, str]],
        identifiers: set[tuple[str, str]],
        disabled_by: DeviceEntryDisabler | UndefinedType | None,
    ) -> DeviceEntry:
        """Create DeviceEntry from DeletedDeviceEntry."""
        disabled_by = self._calculate_disable_by(config_entry, disabled_by)
        return DeviceEntry(
            area_id=self.area_id,
            config_entry_id=config_entry.entry_id,
            config_subentry_id=config_subentry_id,
            # type ignores: likely https://github.com/python/mypy/issues/8625
            connections=connections,  # type: ignore[arg-type]
            created_at=self.created_at,
            disabled_by=disabled_by,
            identifiers=identifiers,  # type: ignore[arg-type]
            id=self.id,
            labels=self.labels,  # type: ignore[arg-type]
            name_by_user=self.name_by_user,
        )

    def to_child_device_entry(
        self,
        config_entry: ConfigEntry,
        config_subentry_id: str | None,
        identifiers: set[tuple[str, str]],
        disabled_by: DeviceEntryDisabler | UndefinedType | None,
        parent_device: DeviceEntry,
    ) -> ChildDeviceEntry:
        """Create ChildDeviceEntry from DeletedDeviceEntry."""
        disabled_by = self._calculate_disable_by(config_entry, disabled_by)
        # Re-derive parent-device disable from the (possibly different)
        # parent device.
        if (
            self.disabled_by is not UNDEFINED
            and disabled_by is None
            and parent_device.disabled
        ):
            disabled_by = DeviceEntryDisabler.DEVICE
        return ChildDeviceEntry(
            area_id=self.area_id,
            config_entry_id=config_entry.entry_id,
            config_subentry_id=config_subentry_id,
            created_at=self.created_at,
            disabled_by=disabled_by,
            # type ignores: likely https://github.com/python/mypy/issues/8625
            identifiers=identifiers,  # type: ignore[arg-type]
            id=self.id,
            labels=self.labels,  # type: ignore[arg-type]
            name_by_user=self.name_by_user,
            parent_device_id=parent_device.id,
        )

    @under_cached_property
    def as_storage_fragment(self) -> json_fragment:
        """Return a json fragment for storage."""
        return json_fragment(
            json_bytes(
                {
                    "area_id": self.area_id,
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
                    "domain": self.domain,
                }
            )
        )


def _copy_if_exists(source: str, destination: str) -> bool:
    """Copy source to destination when source exists (runs in the executor).

    Returns whether the file was copied.
    """
    if not os.path.isfile(source):
        return False
    shutil.copyfile(source, destination)
    return True


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
        # Note: There's no version 2, it was planned and supported by previous versions
        # of the migrator which treated version 2 like version 1.
        if old_major_version < 3:
            # Copy the store before the version 3 migrator rewrites every device, so a
            # user can recover the pre-migration registry if the migration misbehaves.
            await self._async_backup_store()
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
            # Version 3 restricts a device to a single config entry and subentry,
            # introduced in 2026.8. Composite devices which belonged to several
            # config entries (or several subentries of one entry) are split into one
            # device per (config entry, subentry). Each split device keeps a copy of
            # the identifiers and connections and a reference (composite_device_id) to the original
            # composite device id, so that actions targeting the old id still reach
            # all split devices. Entities are moved to the matching split device when
            # the registries are loaded.
            migrated_at = utcnow().isoformat()
            devices: list[dict[str, Any]] = []
            # Active splits whose copied disabled_by must be reconciled against their
            # single config entry once the config entries are loaded
            migrated_active_splits: list[dict[str, Any]] = []
            for device in old_data["devices"]:
                # One target per config entry. config_entries_subentries was a set, so
                # the old model allowed a device in several subentries of one config
                # entry, but the single-owner model keeps one. Multi-subentry devices
                # created by core integrations all come from broken subentry migrators
                # (which left a device in both None and its real subentry), so prefer
                # a real subentry over the main entry (None). Collapsing rather than
                # splitting avoids duplicate devices which, sharing identifiers and
                # connections within one config entry, would collide in the
                # per-config-entry identifier/connection index.
                pairs = [
                    (
                        config_entry_id,
                        next((s for s in subentry_ids if s is not None), None),
                    )
                    for config_entry_id, subentry_ids in device[
                        "config_entries_subentries"
                    ].items()
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
                    devices.append(device)
                    continue
                old_id = device["id"]
                composite_primary = device.get("primary_config_entry")
                for config_entry_id, subentry_id in pairs:
                    split = copy.deepcopy(device)
                    split["id"] = uuid_util.random_uuid_hex()
                    split["config_entry_id"] = config_entry_id
                    split["config_subentry_id"] = subentry_id
                    split["primary_config_entry"] = config_entry_id
                    split["composite_device_id"] = old_id
                    split["composite_primary_config_entry"] = composite_primary
                    split["split_at"] = migrated_at
                    split["has_composite_identifiers"] = True
                    devices.append(split)
                    migrated_active_splits.append(split)
            old_data["devices"] = devices
            # A split inherited the composite's disabled_by, which may not match its
            # single config entry (e.g. a split owned by an enabled entry must not stay
            # CONFIG_ENTRY disabled). Config entries load concurrently, so wait for them
            # and reconcile each split against its own entry.
            if migrated_active_splits:
                await self.hass.config_entries.async_wait_initialized()
                for split in migrated_active_splits:
                    config_entry = self.hass.config_entries.async_get_entry(
                        split["config_entry_id"]
                    )
                    if config_entry is not None:
                        _migrate_device_disabled_by(
                            split, config_entry.disabled_by is not None
                        )

            deleted_devices: list[dict[str, Any]] = []
            for device in old_data["deleted_devices"]:
                # One target per config entry. config_entries_subentries was a set, so
                # the old model allowed a device in several subentries of one config
                # entry, but the single-owner model keeps one. Multi-subentry devices
                # created by core integrations all come from broken subentry migrators
                # (which left a device in both None and its real subentry), so prefer
                # a real subentry over the main entry (None). Collapsing rather than
                # splitting avoids duplicate devices which, sharing identifiers and
                # connections within one config entry, would collide in the
                # per-config-entry identifier/connection index.
                pairs = [
                    (
                        config_entry_id,
                        next((s for s in subentry_ids if s is not None), None),
                    )
                    for config_entry_id, subentry_ids in device[
                        "config_entries_subentries"
                    ].items()
                ]
                if len(pairs) <= 1:
                    # Unlike active devices, config_entry_id=None is a valid
                    # (orphaned) state for a deleted device, so a deleted device with
                    # no config entries is kept rather than dropped.
                    config_entry_id, subentry_id = pairs[0] if pairs else (None, None)
                    device["config_entry_id"] = config_entry_id
                    device["config_subentry_id"] = subentry_id
                    device["domain"] = None
                    deleted_devices.append(device)
                    continue
                # A deleted device that belonged to several config entries or subentries
                # is split like an active one - each split keeps a copy of the
                # identifiers/connections so every config entry can still restore its
                # share when a matching device is re-registered.
                for config_entry_id, subentry_id in pairs:
                    split = copy.deepcopy(device)
                    split["id"] = uuid_util.random_uuid_hex()
                    split["config_entry_id"] = config_entry_id
                    split["config_subentry_id"] = subentry_id
                    split["domain"] = None
                    deleted_devices.append(split)
            old_data["deleted_devices"] = deleted_devices
            # config_entries and config_entries_subentries are deprecated; v3 stores only
            # the singular config_entry_id / config_subentry_id (single-entry devices kept
            # the old keys, splits copied them via deepcopy).
            for migrated in (*devices, *deleted_devices):
                migrated.pop("config_entries", None)
                migrated.pop("config_entries_subentries", None)

        if old_major_version < 3 or (old_major_version == 3 and old_minor_version < 2):
            # Version 3.2, introduced in 2026.8, rewrites via_device_id links that do
            # not reference a live device. A link to a composite parent split by the
            # version 3 migration is remapped to one of the splits; any other stale
            # link is detached.
            device_ids = {device["id"] for device in old_data["devices"]}
            # old composite id -> {config entry id -> split id}
            composite_splits: dict[str, dict[str, str]] = {}
            for device in old_data["devices"]:
                if (composite_id := device["composite_device_id"]) is not None:
                    composite_splits.setdefault(composite_id, {})[
                        device["config_entry_id"]
                    ] = device["id"]

            def _split_for_via_device(
                config_entry_id: str, splits: dict[str, str]
            ) -> str:
                """Pick the split for via device: same entry, same domain, any."""
                if (split_id := splits.get(config_entry_id)) is not None:
                    return split_id
                config_entries = self.hass.config_entries
                self_entry = config_entries.async_get_entry(config_entry_id)
                if self_entry is not None:
                    for split_entry_id, split_id in splits.items():
                        split_entry = config_entries.async_get_entry(split_entry_id)
                        if (
                            split_entry is not None
                            and split_entry.domain == self_entry.domain
                        ):
                            return split_id
                return next(iter(splits.values()))

            stale_via_devices = [
                device
                for device in old_data["devices"]
                if device["via_device_id"] is not None
                and device["via_device_id"] not in device_ids
            ]
            # The domain rung of the split resolution needs the config entries, which
            # load concurrently, so wait for them only when a link must be remapped
            if any(
                device["via_device_id"] in composite_splits
                for device in stale_via_devices
            ):
                await self.hass.config_entries.async_wait_initialized()
            for device in stale_via_devices:
                if (
                    splits := composite_splits.get(device["via_device_id"])
                ) is not None:
                    device["via_device_id"] = _split_for_via_device(
                        device["config_entry_id"], splits
                    )
                else:
                    device["via_device_id"] = None

        if old_major_version < 3 or (old_major_version == 3 and old_minor_version < 3):
            # Version 3.3, introduced in 2026.8, clears via_device_id self-references,
            # which are no longer allowed.
            for device in old_data["devices"]:
                if device["via_device_id"] == device["id"]:
                    device["via_device_id"] = None

        if old_major_version < 3 or (old_major_version == 3 and old_minor_version < 4):
            # Version 3.4 adds child devices, introduced in 2026.9
            old_data.setdefault("child_devices", [])

        if old_major_version > 3:
            raise NotImplementedError
        return old_data

    async def _async_backup_store(self) -> None:
        """Copy the store file to a timestamped backup before migrating."""
        source = self.path
        backup = f"{source}.{utcnow().strftime('%Y%m%d_%H%M%S')}.migration_backup"
        try:
            copied = await self.hass.async_add_executor_job(
                _copy_if_exists, source, backup
            )
        except OSError as err:
            _LOGGER.warning("Could not back up %s before migration: %s", source, err)
        else:
            if copied:
                _LOGGER.info("Backed up %s to %s before migration", source, backup)


class _CollidingKeys(NamedTuple):
    """Identifiers and connections shared with a colliding device."""

    identifiers: set[tuple[str, str]]
    connections: set[tuple[str, str]]


class DeviceRegistryItems[_EntryTypeT: (DeviceEntry, DeletedDeviceEntry)](
    BaseRegistryItems[_EntryTypeT]
):
    """Container for device registry items, maps device id -> entry.

    Maintains two additional indexes. An identifier or connection can be shared by
    several devices, each belonging to a different config entry, so each index maps a
    connection or identifier to the devices that have it, keyed by config entry id:
    - (connection_type, connection identifier) -> {config_entry_id: entry}
    - (DOMAIN, identifier) -> {config_entry_id: entry}

    Registry bugs used to allow duplicate keys within a config entry, so old stores
    can hold them. Only the last indexed device occupies the slot (matching historic
    lookup behavior); the others are recorded as shadowed until collisions are
    reconciled:
    - (config_entry_id, (connection_type, connection identifier)) -> {device_id}
    - (config_entry_id, (DOMAIN, identifier)) -> {device_id}
    """

    def __init__(self) -> None:
        """Initialize the container."""
        super().__init__()
        self._connections: dict[tuple[str, str], dict[str | None, _EntryTypeT]] = {}
        self._identifiers: dict[tuple[str, str], dict[str | None, _EntryTypeT]] = {}
        self._shadowed_connections: dict[
            tuple[str | None, tuple[str, str]], set[str]
        ] = {}
        self._shadowed_identifiers: dict[
            tuple[str | None, tuple[str, str]], set[str]
        ] = {}

    @override
    def _index_entry(self, key: str, entry: _EntryTypeT) -> None:
        """Index an entry."""
        for connection in entry.connections:
            self._index_key(
                connection,
                entry,
                self._connections,
                self._shadowed_connections,
            )
        for identifier in entry.identifiers:
            self._index_key(
                identifier,
                entry,
                self._identifiers,
                self._shadowed_identifiers,
            )

    def _index_key(
        self,
        key: tuple[str, str],
        new_device: _EntryTypeT,
        index: dict[tuple[str, str], dict[str | None, _EntryTypeT]],
        shadowed_index: dict[tuple[str | None, tuple[str, str]], set[str]],
    ) -> None:
        """Index one key, recording a displaced device as shadowed."""
        by_config_entry = index.setdefault(key, {})
        config_entry_id = new_device.config_entry_id
        if (
            existing := by_config_entry.get(config_entry_id)
        ) is not None and existing.id != new_device.id:
            shadowed_index.setdefault((config_entry_id, key), set()).add(existing.id)
        by_config_entry[config_entry_id] = new_device

    @override
    def _unindex_entry(
        self, key: str, replacement_entry: _EntryTypeT | None = None
    ) -> None:
        """Unindex an entry."""
        old_device = self.data[key]
        for connection in old_device.connections:
            self._unindex_key(
                connection,
                old_device,
                self._connections,
                self._shadowed_connections,
            )
        for identifier in old_device.identifiers:
            self._unindex_key(
                identifier,
                old_device,
                self._identifiers,
                self._shadowed_identifiers,
            )

    def _unindex_key(
        self,
        key: tuple[str, str],
        old_device: _EntryTypeT,
        index: dict[tuple[str, str], dict[str | None, _EntryTypeT]],
        shadowed_index: dict[tuple[str | None, tuple[str, str]], set[str]],
    ) -> None:
        """Unindex one key, promoting a shadowed device into the slot."""
        by_config_entry = index[key]
        config_entry_id = old_device.config_entry_id
        shadow_key = (config_entry_id, key)
        shadowed_ids = shadowed_index.get(shadow_key)

        if by_config_entry[config_entry_id] is old_device:
            if shadowed_ids:
                by_config_entry[config_entry_id] = self.data[shadowed_ids.pop()]
            else:
                del by_config_entry[config_entry_id]
                if not by_config_entry:
                    del index[key]
        else:
            # Not the slot holder, so it must be shadowed
            assert shadowed_ids is not None
            shadowed_ids.remove(old_device.id)

        if shadowed_ids is not None and not shadowed_ids:
            del shadowed_index[shadow_key]

    def get_entry(
        self,
        identifiers: set[tuple[str, str]] | None = None,
        connections: set[tuple[str, str]] | None = None,
        *,
        config_entry_id: str | UndefinedType | None = UNDEFINED,
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
        identifiers: AbstractSet[tuple[str, str]] | None = None,
        connections: AbstractSet[tuple[str, str]] | None = None,
        *,
        config_entry_id: str | None = None,
    ) -> list[_EntryTypeT]:
        """Get all entries matching identifiers or connections.

        Matches across all config entries, or only within one if config_entry_id
        is given.
        """
        entries: dict[str, _EntryTypeT] = {}
        if identifiers:
            for identifier in identifiers:
                if (by_config_entry := self._identifiers.get(identifier)) is not None:
                    if config_entry_id is None:
                        for entry in by_config_entry.values():
                            entries[entry.id] = entry
                    elif (scoped := by_config_entry.get(config_entry_id)) is not None:
                        entries[scoped.id] = scoped
        if connections:
            for connection in _normalize_connections(connections):
                if (by_config_entry := self._connections.get(connection)) is not None:
                    if config_entry_id is None:
                        for entry in by_config_entry.values():
                            entries[entry.id] = entry
                    elif (scoped := by_config_entry.get(config_entry_id)) is not None:
                        entries[scoped.id] = scoped
        return list(entries.values())

    def get_colliding_device_ids(
        self,
        identifiers: set[tuple[str, str]],
        connections: set[tuple[str, str]],
        *,
        config_entry_id: str,
        exclude_device_id: str | None,
    ) -> dict[str, _CollidingKeys]:
        """Get the ids of other same-config-entry devices holding the given keys.

        Returns a map from the id of each colliding device to the identifiers and
        connections it shares with the given ones. Includes devices shadowed in the
        index. connections must be normalized.
        """
        colliding: dict[str, _CollidingKeys] = {}
        for identifier in identifiers:
            for holder_id in self._holder_device_ids(
                identifier,
                config_entry_id,
                self._identifiers,
                self._shadowed_identifiers,
            ):
                if holder_id != exclude_device_id:
                    colliding.setdefault(
                        holder_id, _CollidingKeys(set(), set())
                    ).identifiers.add(identifier)
        for connection in connections:
            for holder_id in self._holder_device_ids(
                connection,
                config_entry_id,
                self._connections,
                self._shadowed_connections,
            ):
                if holder_id != exclude_device_id:
                    colliding.setdefault(
                        holder_id, _CollidingKeys(set(), set())
                    ).connections.add(connection)
        return colliding

    def _holder_device_ids(
        self,
        key: tuple[str, str],
        config_entry_id: str,
        index: dict[tuple[str, str], dict[str | None, _EntryTypeT]],
        shadowed_index: dict[tuple[str | None, tuple[str, str]], set[str]],
    ) -> list[str]:
        """Get a list of ids of the config entry's devices holding a key."""
        holder_device_ids: list[str] = []
        if (by_config_entry := index.get(key)) is not None and (
            slot_holder := by_config_entry.get(config_entry_id)
        ) is not None:
            holder_device_ids.append(slot_holder.id)
        holder_device_ids.extend(shadowed_index.get((config_entry_id, key), ()))
        return holder_device_ids

    def count_shadowed_keys(self) -> int:
        """Count keys registered to multiple devices of one config entry."""
        return sum(
            len(device_ids)
            for shadowed_index in (
                self._shadowed_connections,
                self._shadowed_identifiers,
            )
            for device_ids in shadowed_index.values()
        )


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

    def get_composite_splits(self) -> dict[str, list[DeviceEntry]]:
        """Get the pre-migration composite device ids and the devices split from them."""
        data = self.data
        return {
            composite_device_id: [data[key] for key in keys]
            for composite_device_id, keys in self._composite_device_id_index.items()
        }


class _DeprecatedDeviceRegistryItemsView:
    """Backwards-compatible view returned by the `DeviceRegistry.devices` property.

    Can be removed in release 2027.9.

    Iterating this yields the `DeviceEntry` values, which is the supported way to
    enumerate the registry (`for entry in registry.devices`, `list(registry.devices)`
    and similar). Using it as a mapping - subscription, device-id membership,
    `.values()`, `.get()`, `.get_entry()` and the other container methods - is
    deprecated: each such access is reported via `report_usage` (raising for core code
    and core integrations, warning for custom integrations) and then delegated to the
    underlying container.
    """

    __slots__ = ("_devices",)

    def __init__(self, devices: ActiveDeviceRegistryItems) -> None:
        """Initialize the view over a device registry."""
        self._devices = devices

    def __iter__(self) -> Iterator[DeviceEntry]:
        """Iterate over the device entries."""
        return iter(self._devices.values())

    def __len__(self) -> int:
        """Return the number of device entries."""
        return len(self._devices)

    def _report_deprecated_use(self) -> None:
        """Report deprecated use of `DeviceRegistry.devices`."""
        report_usage(
            "uses `device_registry.devices` as a mapping or calls its lookup "
            "methods, which is deprecated; iterate it to get the device entries, "
            "or use `async_get`, `async_entries_for_config_entry` and similar "
            "helpers for lookups",
            breaks_in_ha_version="2027.9.0",
            core_behavior=ReportBehavior.ERROR,
            core_integration_behavior=ReportBehavior.ERROR,
            custom_integration_behavior=ReportBehavior.LOG,
        )

    def __getitem__(self, key: str) -> DeviceEntry:
        """Return the device entry for a device id (deprecated)."""
        self._report_deprecated_use()
        return self._devices[key]

    def __contains__(self, obj: object) -> bool:
        """Return whether a device entry - or, deprecated, a device id - is registered.

        Value membership (`DeviceEntry in registry.devices`) is the supported use and
        matches the `Collection[DeviceEntry]` type. Membership by device id (a `str`)
        is the old key-based mapping behavior and is deprecated.
        """
        # DeviceEntry is never subclassed, a direct type check is safe
        if type(obj) is DeviceEntry:
            return self._devices.get(obj.id) == obj
        if isinstance(obj, str):
            self._report_deprecated_use()
            return obj in self._devices
        return False

    def __getattr__(self, name: str) -> Any:
        """Delegate the remaining mapping methods to the container (deprecated)."""
        # Private and dunder names are never proxied.
        if name.startswith("_"):
            raise AttributeError(name)
        self._report_deprecated_use()
        return getattr(self._devices, name)


class ChildDeviceRegistryItems(BaseRegistryItems[ChildDeviceEntry]):
    """Container for child device registry entries, maps child device id -> entry.

    Maintains five additional indexes. Identifiers are unique per config entry,
    shared with the parent devices' identifier namespace:
    - (DOMAIN, identifier) -> {config_entry_id: entry}
    - parent_device_id -> dict[key, True]
    - config_entry_id -> dict[key, True]
    - area_id -> dict[key, True] (explicitly set areas only, not inherited ones)
    - label -> dict[key, True]
    """

    def __init__(self) -> None:
        """Initialize the container."""
        super().__init__()
        self._identifiers: dict[tuple[str, str], dict[str, ChildDeviceEntry]] = {}
        self._parent_device_id_index: RegistryIndexType = defaultdict(dict)
        self._config_entry_id_index: RegistryIndexType = defaultdict(dict)
        self._area_id_index: RegistryIndexType = defaultdict(dict)
        self._labels_index: RegistryIndexType = defaultdict(dict)

    @override
    def _index_entry(self, key: str, entry: ChildDeviceEntry) -> None:
        """Index an entry."""
        # Unlike DeviceRegistryItems, this identifier index has no shadow tracking, so
        # two same-entry children sharing an identifier let the last indexed own the
        # slot. Normal operation can't reach this: _validate_child_identifiers rejects a
        # same-entry identifier collision before insert. It's only possible via a
        # hand-edited or corrupt store, and is acceptable (the slot stays consistent
        # because _unindex_entry only clears the slot it still holds).
        for identifier in entry.identifiers:
            self._identifiers.setdefault(identifier, {})[entry.config_entry_id] = entry
        self._parent_device_id_index[entry.parent_device_id][key] = True
        self._config_entry_id_index[entry.config_entry_id][key] = True
        if (area_id := entry.area_id) is not None:
            self._area_id_index[area_id][key] = True
        for label in entry.labels:
            self._labels_index[label][key] = True

    @override
    def _unindex_entry(
        self, key: str, replacement_entry: ChildDeviceEntry | None = None
    ) -> None:
        """Unindex an entry."""
        entry = self.data[key]
        for identifier in entry.identifiers:
            by_config_entry = self._identifiers.get(identifier)
            if (
                by_config_entry is not None
                and by_config_entry.get(entry.config_entry_id) is entry
            ):
                del by_config_entry[entry.config_entry_id]
                if not by_config_entry:
                    del self._identifiers[identifier]
        self._unindex_entry_value(
            key, entry.parent_device_id, self._parent_device_id_index
        )
        self._unindex_entry_value(
            key, entry.config_entry_id, self._config_entry_id_index
        )
        if (area_id := entry.area_id) is not None:
            self._unindex_entry_value(key, area_id, self._area_id_index)
        for label in entry.labels:
            self._unindex_entry_value(key, label, self._labels_index)

    def get_entry(
        self,
        identifiers: set[tuple[str, str]],
        *,
        config_entry_id: str,
    ) -> ChildDeviceEntry | None:
        """Get the first child device matching an identifier within the config entry."""
        for identifier in identifiers:
            if (
                by_config_entry := self._identifiers.get(identifier)
            ) is not None and config_entry_id in by_config_entry:
                return by_config_entry[config_entry_id]
        return None

    def get_children_for_device_id(
        self, parent_device_id: str
    ) -> list[ChildDeviceEntry]:
        """Get the child devices of a parent device."""
        data = self.data
        return [
            data[key] for key in self._parent_device_id_index.get(parent_device_id, ())
        ]

    def get_devices_for_config_entry_id(
        self, config_entry_id: str
    ) -> list[ChildDeviceEntry]:
        """Get child devices for config entry."""
        data = self.data
        return [
            data[key] for key in self._config_entry_id_index.get(config_entry_id, ())
        ]

    def get_devices_for_area_id(self, area_id: str) -> list[ChildDeviceEntry]:
        """Get child devices with an explicitly set area."""
        data = self.data
        return [data[key] for key in self._area_id_index.get(area_id, ())]

    def get_devices_for_label(self, label: str) -> list[ChildDeviceEntry]:
        """Get child devices for label."""
        data = self.data
        return [data[key] for key in self._labels_index.get(label, ())]


class DeletedDeviceRegistryItems(DeviceRegistryItems[DeletedDeviceEntry]):
    """Container for deleted device registry entries.

    A deleted device that still belongs to a config entry is indexed by config entry id in
    the base class, like an active device. An orphaned deleted device (its config entry
    removed) has no config entry id and would collide with every other orphan in the base
    config_entry_id=None slot, so orphans are kept out of the base index and tracked in a
    separate index keyed by device id, which is unique so orphans never shadow each other.
    Orphans are matched on restore by get_orphaned_entry.
    """

    def __init__(self) -> None:
        """Initialize the container."""
        super().__init__()
        self._orphaned_connections: dict[
            tuple[str, str], dict[str, DeletedDeviceEntry]
        ] = {}
        self._orphaned_identifiers: dict[
            tuple[str, str], dict[str, DeletedDeviceEntry]
        ] = {}

    @override
    def _index_entry(self, key: str, entry: DeletedDeviceEntry) -> None:
        """Index an entry, keeping orphans in the separate id-keyed index."""
        if entry.config_entry_id is not None:
            super()._index_entry(key, entry)
            return
        for connection in entry.connections:
            self._orphaned_connections.setdefault(connection, {})[entry.id] = entry
        for identifier in entry.identifiers:
            self._orphaned_identifiers.setdefault(identifier, {})[entry.id] = entry

    @override
    def _unindex_entry(
        self, key: str, replacement_entry: DeletedDeviceEntry | None = None
    ) -> None:
        """Unindex an entry from the base or the orphan index."""
        entry = self.data[key]
        if entry.config_entry_id is not None:
            super()._unindex_entry(key, replacement_entry)
            return
        for connection in entry.connections:
            if connection in self._orphaned_connections:
                del self._orphaned_connections[connection][entry.id]
                if not self._orphaned_connections[connection]:
                    del self._orphaned_connections[connection]
        for identifier in entry.identifiers:
            if identifier in self._orphaned_identifiers:
                del self._orphaned_identifiers[identifier][entry.id]
                if not self._orphaned_identifiers[identifier]:
                    del self._orphaned_identifiers[identifier]

    def get_orphaned_entry(
        self,
        identifiers: set[tuple[str, str]] | None,
        connections: set[tuple[str, str]] | None,
        domain: str,
    ) -> DeletedDeviceEntry | None:
        """Return an orphan of the given domain to restore.

        Orphans are matched on their recorded domain so a chance identifier or connection
        collision doesn't restore another integration's device. A domain-less orphan
        (carried over by the migration with no recoverable domain) is left for the
        periodic purge rather than restored.
        """
        orphans: dict[str, DeletedDeviceEntry] = {}
        for identifier in identifiers or ():
            orphans.update(self._orphaned_identifiers.get(identifier, {}))
        for connection in _normalize_connections(connections or set()):
            orphans.update(self._orphaned_connections.get(connection, {}))
        for entry in orphans.values():
            if entry.domain == domain:
                return entry
        return None


class DeviceRegistry(BaseRegistry[dict[str, list[dict[str, Any]]]]):
    """Class to hold a registry of devices."""

    _devices: ActiveDeviceRegistryItems
    devices: Collection[DeviceEntry]
    _child_devices: ChildDeviceRegistryItems
    child_devices: Collection[ChildDeviceEntry]
    _deleted_devices: DeletedDeviceRegistryItems
    _device_data: dict[str, DeviceEntry]
    _child_device_data: dict[str, ChildDeviceEntry]

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the device registry."""
        self.hass = hass
        # Devices registered through async_get_or_create in the current setup session
        # of their config entry, keyed by config entry id. A key collision with one of
        # these raises; one with a not yet registered device is reconciled.
        self._live_device_ids: dict[str, set[str]] = {}
        self._loaded_event = asyncio.Event()
        self._store = DeviceRegistryStore(
            hass,
            STORAGE_VERSION_MAJOR,
            STORAGE_KEY,
            atomic_writes=True,
            minor_version=STORAGE_VERSION_MINOR,
            serialize_in_event_loop=False,
        )

    @property
    def deleted_devices(self) -> DeletedDeviceRegistryItems:
        """Return the deleted devices container (deprecated).

        Can be removed in release 2027.9.
        """
        report_usage(
            "accesses `device_registry.deleted_devices`, which is deprecated and "
            "an internal implementation detail of the device registry",
            breaks_in_ha_version="2027.9.0",
            core_behavior=ReportBehavior.ERROR,
            core_integration_behavior=ReportBehavior.ERROR,
            custom_integration_behavior=ReportBehavior.LOG,
        )
        return self._deleted_devices

    @overload
    def async_get(
        self,
        device_id: str,
        *,
        include_child_devices: Literal[False],
        include_main_devices: bool = True,
        include_composite_devices: bool = True,
    ) -> DeviceEntry | None: ...

    @overload
    def async_get(
        self,
        device_id: str,
        *,
        include_child_devices: Literal[True] = True,
        include_main_devices: Literal[False],
        include_composite_devices: Literal[False],
    ) -> ChildDeviceEntry | None: ...

    @overload
    def async_get(
        self,
        device_id: str,
        *,
        include_child_devices: Literal[True] = True,
        include_main_devices: Literal[False],
        include_composite_devices: Literal[True] = True,
    ) -> AnyDeviceEntry | None: ...

    @overload
    def async_get(
        self,
        device_id: str,
        *,
        include_child_devices: Literal[True] = True,
        include_main_devices: Literal[True] = True,
        include_composite_devices: bool = True,
    ) -> AnyDeviceEntry | None: ...

    @callback
    def async_get(
        self,
        device_id: str,
        *,
        include_child_devices: bool = True,
        include_main_devices: bool = True,
        include_composite_devices: bool = True,
    ) -> AnyDeviceEntry | None:
        """Get device or child device.

        We retrieve the entry from the underlying dicts to avoid
        the overhead of the UserDict __getitem__.

        For a pre-migration composite device id, a read-only composite device
        merged from the split devices is returned, so integration code that resolves a
        device by id (e.g. in a service handler) keeps working. The composite is
        synthesized on demand and never stored, so it stays invisible to enumeration,
        identifier search and the frontend device list.

        With include_child_devices=False a child-device id resolves to None (the child
        is treated as absent) and the return type excludes children. With
        include_main_devices=False a main-device id resolves to None. With
        include_composite_devices=False a composite-device id resolves to None.
        """
        if (
            include_main_devices
            and (device := self._device_data.get(device_id)) is not None
        ):
            return device
        if (
            include_child_devices
            and (child_device := self._child_device_data.get(device_id)) is not None
        ):
            return child_device
        if include_composite_devices and (
            split_devices := self._devices.get_devices_for_composite_device_id(
                device_id
            )
        ):
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
    ) -> DeviceEntry | None:
        """Check if a device is registered.

        Searches main devices only; a child device is found via
        async_get_child_device_by_identifier.

        Identifiers and connections are unique per config entry. If several config
        entries share the looked-up identifier or connection, the match is resolved to a
        single device when possible - preferring the device whose config entry domain
        matches the looked-up identifier. If the remaining matches are the splits of one
        pre-migration composite device, a read-only composite spanning them is returned
        (async_update_device and async_remove_device fan it out to the underlying
        devices). Otherwise, for independent devices sharing an identifier or connection,
        one owned by the calling integration is preferred, falling back to the first
        match.
        """
        report_usage(
            "calls `device_registry.async_get_device`, which is deprecated because "
            "device identifiers and connections are no longer unique across config "
            "entries; use `async_get_device_by_identifier`, "
            "`async_get_device_by_connection` or `async_get_devices` instead",
            core_behavior=ReportBehavior.ERROR,
            core_integration_behavior=ReportBehavior.ERROR,
            breaks_in_ha_version="2027.8.0",
        )
        matches = self._async_matching_devices(identifiers, connections)
        if len(matches) <= 1:
            return matches[0] if matches else None
        # If the matches are the splits of one pre-migration composite device, return a
        # read-only composite over them, reusing the composite's id so stored references
        # (an automation, a fired event, or an entity holding the old device id) keep
        # resolving to it as before the split.
        composite_device_ids = {match.composite_device_id for match in matches}
        if (
            len(composite_device_ids) == 1
            and (pre_migration_id := next(iter(composite_device_ids))) is not None
        ):
            return self._restore_composite_device(pre_migration_id, matches)
        # Otherwise they are independent devices sharing an identifier or connection.
        # Prefer one owned by the calling integration so the caller resolves to its own
        # device rather than an insertion-order-dependent one; fall back to the first.
        if (domain := _current_integration_domain()) is not None and (
            device := self._first_device_in_domain(matches, domain)
        ) is not None:
            return device
        return matches[0]

    @callback
    def async_get_device_by_identifier(
        self, identifier: tuple[str, str], config_entry_id: str
    ) -> DeviceEntry | None:
        """Get the device with the identifier, owned by the config entry.

        Searches main devices only; use async_get_child_device_by_identifier for a
        child device.
        Identifiers are unique within a config entry, so unlike async_get_device
        the lookup cannot be ambiguous.
        """
        return self._devices.get_entry(
            identifiers={identifier}, config_entry_id=config_entry_id
        )

    @callback
    def async_get_child_device_by_identifier(
        self, identifier: tuple[str, str], config_entry_id: str
    ) -> ChildDeviceEntry | None:
        """Get the child device with the identifier, owned by the config entry.

        Identifiers are unique within a config entry, so the lookup cannot be
        ambiguous.
        """
        return self._child_devices.get_entry(
            identifiers={identifier}, config_entry_id=config_entry_id
        )

    @callback
    def async_get_device_by_connection(
        self, connection: tuple[str, str], config_entry_id: str
    ) -> DeviceEntry | None:
        """Get the device with the connection, owned by the config entry.

        Connections are unique within a config entry, so unlike async_get_device
        the lookup cannot be ambiguous.
        """
        return self._devices.get_entry(
            connections={connection}, config_entry_id=config_entry_id
        )

    @callback
    def async_get_devices(
        self,
        *,
        identifiers: set[tuple[str, str]] | None = None,
        connections: set[tuple[str, str]] | None = None,
        config_entry_id: str | None = None,
    ) -> list[DeviceEntry]:
        """Get all devices matching any of the identifiers or connections.

        Searches main devices only; a child device is found via
        async_get_child_device_by_identifier.
        If config_entry_id is given, only devices owned by that config entry are
        returned.
        """
        return self._devices.get_entries(
            identifiers, connections, config_entry_id=config_entry_id
        )

    def _first_device_in_domain(
        self, devices: Iterable[DeviceEntry], domain: str
    ) -> DeviceEntry | None:
        """Return the first device whose config entry belongs to domain."""
        for device in devices:
            entry = self.hass.config_entries.async_get_entry(device.config_entry_id)
            if entry is not None and entry.domain == domain:
                return device
        return None

    @callback
    def _async_matching_devices(
        self,
        identifiers: AbstractSet[tuple[str, str]] | None,
        connections: AbstractSet[tuple[str, str]] | None,
    ) -> list[DeviceEntry]:
        """Return devices matching the lookup, narrowed by identifier-domain priority."""
        matches = self._devices.get_entries(identifiers, connections)
        if len(matches) > 1 and identifiers:
            domains = {identifier[0] for identifier in identifiers}
            preferred = [
                device
                for device in matches
                if (
                    entry := self.hass.config_entries.async_get_entry(
                        device.config_entry_id
                    )
                )
                and entry.domain in domains
            ]
            if preferred:
                return preferred
        return matches

    @callback
    def _async_device_ids_for_composite_device_id(
        self, device_id: str
    ) -> list[str] | None:
        """Return the underlying real device ids if device_id is a composite."""
        if device_id in self._devices:
            return None
        if split_devices := self._devices.get_devices_for_composite_device_id(
            device_id
        ):
            return [split_device.id for split_device in split_devices]
        return None

    @callback
    def async_get_devices_for_composite_device_id(
        self, composite_device_id: str
    ) -> list[DeviceEntry]:
        """Return the devices a composite device id represents.

        A composite device id is a pre-migration composite id - a device that belonged to
        several config entries, split into one device per config entry, each keeping the
        original id as composite_device_id. The underlying live devices are returned so
        that actions and entity lookups targeting the composite id still reach all of
        them; unmodified integrations keep the pre-rewrite behaviour, where a shared
        identifier/connection resolved to a single multi-config-entry device. Returns an
        empty list for a device id which is not a composite device id.
        """
        return self._devices.get_devices_for_composite_device_id(composite_device_id)

    @callback
    def async_is_composite_device_id(self, device_id: str) -> bool | None:
        """Return True if device_id is a pre-migration composite device id.

        A composite device was split into one device per config entry; the
        composite device id no longer refers to a registered device. Returns
        False for a registered device id, and None for an unknown id.
        """
        report_usage(
            "calls `device_registry.async_is_composite_device_id`, which is "
            "deprecated; use `async_get` with `include_composite_devices=False` "
            "instead - a composite device id resolves with `async_get(device_id)` but "
            "not with `async_get(device_id, include_composite_devices=False)`",
            core_behavior=ReportBehavior.ERROR,
            core_integration_behavior=ReportBehavior.ERROR,
            breaks_in_ha_version="2027.9.0",
        )
        if device_id in self._devices:
            return False
        if self._devices.get_devices_for_composite_device_id(device_id):
            return True
        return None

    @callback
    def _resolve_via_device_id(
        self, via_device_id: str, config_entry_id: str
    ) -> str | None:
        """Resolve a via_device_id to the id of a registered device.

        The id of a pre-migration composite device is resolved to one of the devices
        it was split into - preferring the split owned by config_entry_id, then one
        owned by the same domain, then any of them. Returns None for an unknown id.
        """
        if via_device_id in self._devices:
            return via_device_id
        if splits := self._devices.get_devices_for_composite_device_id(via_device_id):
            # The composite resolution can be removed in HA Core 2027.8
            report_usage(
                f"passes the id of a pre-migration composite device {via_device_id} "
                "as `via_device_id`; pass the id of a single device instead, e.g. "
                "one returned by async_get_device_by_identifier",
                core_behavior=ReportBehavior.LOG,
                breaks_in_ha_version="2027.8",
            )
            for split in splits:
                if split.config_entry_id == config_entry_id:
                    return split.id
            if (
                config_entry := self.hass.config_entries.async_get_entry(
                    config_entry_id
                )
            ) is not None and (
                split_in_domain := self._first_device_in_domain(
                    splits, config_entry.domain
                )
            ) is not None:
                return split_in_domain.id
            return splits[0].id
        return None

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
    def async_get_or_create(  # noqa: C901
        self,
        *,
        config_entry_id: str,
        config_subentry_id: str | UndefinedType | None = UNDEFINED,
        configuration_url: str | URL | UndefinedType | None = UNDEFINED,
        connections: set[tuple[str, str]] | UndefinedType | None = UNDEFINED,
        # To disable a device if it gets created, does not affect existing devices
        disabled_by: DeviceEntryDisabler | UndefinedType | None = UNDEFINED,
        entry_type: DeviceEntryType | UndefinedType | None = UNDEFINED,
        hw_version: str | UndefinedType | None = UNDEFINED,
        identifiers: set[tuple[str, str]] | UndefinedType | None = UNDEFINED,
        manufacturer: str | UndefinedType | None = UNDEFINED,
        model: str | UndefinedType | None = UNDEFINED,
        model_id: str | UndefinedType | None = UNDEFINED,
        name: str | UndefinedType | None = UNDEFINED,
        serial_number: str | UndefinedType | None = UNDEFINED,
        suggested_area: str | UndefinedType | None = UNDEFINED,
        sw_version: str | UndefinedType | None = UNDEFINED,
        translation_key: str | None = None,
        translation_placeholders: Mapping[str, str] | None = None,
        via_device_id: str | UndefinedType | None = UNDEFINED,
        **kwargs: Any,
    ) -> DeviceEntry:
        """Get device. Create if it doesn't exist.

        To create or update a child device, use async_get_or_create_child.

        If identifiers overlap with a child device, the method raises.
        """
        # Extract deprecated parameters, and reject any other unexpected keyword
        # argument.
        created_at = kwargs.pop("created_at", UNDEFINED)
        default_manufacturer = kwargs.pop("default_manufacturer", UNDEFINED)
        default_model = kwargs.pop("default_model", UNDEFINED)
        default_name = kwargs.pop("default_name", UNDEFINED)
        modified_at = kwargs.pop("modified_at", UNDEFINED)
        via_device = kwargs.pop("via_device", UNDEFINED)
        if kwargs:
            raise TypeError(
                "async_get_or_create() got unexpected keyword arguments "
                f"{', '.join(map(repr, kwargs))}"
            )

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

        if disabled_by is DeviceEntryDisabler.DEVICE:
            raise HomeAssistantError(
                "disabled_by=DeviceEntryDisabler.DEVICE is only valid for a child "
                "device"
            )

        config_entry = self.hass.config_entries.async_get_entry(config_entry_id)
        if config_entry is None:
            raise HomeAssistantError(
                f"Can't link device to unknown config entry {config_entry_id}"
            )

        # Validate before mutating the registry below. `via_device=None` (an explicit
        # "no via device") alongside a via_device_id is contradictory, so reject it too.
        if via_device is not UNDEFINED and via_device_id is not UNDEFINED:
            raise HomeAssistantError(
                "Passing both `via_device` and `via_device_id` is not allowed; "
                "`via_device` is deprecated, pass `via_device_id` only"
            )
        # Report the deprecated parameters here, before any registry mutation.
        deprecated_values = {
            "created_at": created_at,
            "default_manufacturer": default_manufacturer,
            "default_model": default_model,
            "default_name": default_name,
            "modified_at": modified_at,
            "via_device": via_device,
        }
        for parameter, deprecation in _DEPRECATED_DEVICE_INFO_PARAMETERS.items():
            if deprecated_values[parameter] is UNDEFINED:
                continue
            version, replacement = deprecation
            if replacement is None:
                advice = ", which is ignored"
            else:
                advice = f"; use `{replacement}` instead"
            report_usage(
                "calls `device_registry.async_get_or_create` with a deprecated "
                f"`{parameter}` parameter{advice}",
                core_behavior=ReportBehavior.ERROR,
                core_integration_behavior=ReportBehavior.ERROR,
                breaks_in_ha_version=version,
            )
        if (
            config_subentry_id is not UNDEFINED
            and config_subentry_id is not None
            and config_subentry_id not in config_entry.subentries
        ):
            raise HomeAssistantError(
                f"Config entry {config_entry_id} has no subentry {config_subentry_id}"
            )

        if translation_key:
            name = self._resolve_translated_name(
                config_entry, translation_key, translation_placeholders
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

        _validate_device_info(config_entry, device_info)

        if identifiers is None or identifiers is UNDEFINED:
            identifiers = set()

        if connections is None or connections is UNDEFINED:
            connections = set()
        else:
            connections = _normalize_connections(connections)

        # We do not allow registering a device without parent_device_id if the
        # identifiers match an existing child.
        if (
            matched_child_device := self._child_devices.get_entry(
                identifiers=identifiers, config_entry_id=config_entry_id
            )
        ) is not None:
            raise DeviceInfoError(
                config_entry.domain,
                device_info,
                f"identifiers {sorted(identifiers)} overlap with those of child device "
                f"{matched_child_device.id} with identifiers "
                f"{sorted(matched_child_device.identifiers)}",
            )

        device = self._devices.get_entry(
            connections=connections,
            identifiers=identifiers,
            config_entry_id=config_entry_id,
        )

        self._async_reconcile_collisions(
            device,
            config_entry,
            device_info,
            identifiers,
            connections,
        )
        if device is not None:
            # Collision reconciliation can update the matched device (e.g. detach
            # its via link)
            device = self._devices[device.id]

        # Resolved after collision reconciliation so a removed stale duplicate can't be
        # linked
        if via_device_id is not UNDEFINED and via_device_id is not None:
            resolved_via_device_id = self._resolve_via_device_id(
                via_device_id, config_entry_id
            )
            if resolved_via_device_id is None:
                if via_device_id in self._child_device_data:
                    raise DeviceInfoError(
                        config_entry.domain,
                        device_info,
                        f"via_device_id {via_device_id} is a child device, which "
                        "can't be a via device",
                    )
                raise DeviceInfoError(
                    config_entry.domain,
                    device_info,
                    f"via_device_id {via_device_id} is not a registered device id",
                )
            via_device_id = resolved_via_device_id

        is_new = False

        if device is None:
            is_new = True

            deleted_device = self._deleted_devices.get_entry(
                connections=connections,
                identifiers=identifiers,
                config_entry_id=config_entry_id,
            )
            if deleted_device is None:
                # Fall back to an orphan (its owning config entry was removed)
                # so re-adding an integration restores the device id, area, labels and name
                # rather than create a fresh device. Matching on the recorded domain keeps
                # a chance identifier/connection collision from restoring another
                # integration's device.
                deleted_device = self._deleted_devices.get_orphaned_entry(
                    identifiers, connections, config_entry.domain
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
                self._deleted_devices.pop(deleted_device.id)
                device = deleted_device.to_device_entry(
                    config_entry,
                    # Interpret not specifying a subentry as None
                    config_subentry_id if config_subentry_id is not UNDEFINED else None,
                    connections,
                    identifiers,
                    disabled_by,
                )
                disabled_by = UNDEFINED

            self._devices[device.id] = device
            # If creating a new device, default to the config entry name
            if not name or name is UNDEFINED:
                name = config_entry.title

        elif (
            config_subentry_id is not UNDEFINED
            and device.config_subentry_id != config_subentry_id
        ):
            # A device belongs to a single config subentry. Re-registering an existing
            # device under a different subentry of the same config entry (e.g. entities
            # from several subentries sharing one device_info identity) silently moves
            # it. This is deprecated since moves should be explicit via
            # async_update_device(new_config_subentry_id=...).
            # For now warn and fall through to the move below, but it will raise in HA
            # Core 2027.8.
            report_usage(
                "assigns an existing device to a different config subentry, by calling "
                "`async_get_or_create` or by adding entities from several subentries that "
                "share a device; this silently moves the device. A device belongs to one "
                "subentry - keep a shared device in a single subentry, or move it with "
                "`async_update_device`",
                core_behavior=ReportBehavior.LOG,
                breaks_in_ha_version="2027.8.0",
                integration_domain=config_entry.domain,
            )

        self._async_purge_colliding_deleted_devices(device, identifiers, connections)

        if default_manufacturer is not UNDEFINED and device.manufacturer is None:
            validated_fields["manufacturer"] = default_manufacturer

        if default_model is not UNDEFINED and device.model is None:
            validated_fields["model"] = default_model

        if default_name is not UNDEFINED and device.name is None:
            name = default_name

        if via_device is not None and via_device is not UNDEFINED:
            # Resolve the deprecated via_device to a device id. The identifier is not
            # unique across config entries, so prefer a via device in the same config
            # entry, then one from the same integration (domain), falling back to any
            # config entry (a via device may legitimately belong to a different config
            # entry). This ambiguity is why via_device is deprecated.
            via = (
                self._devices.get_entry(
                    identifiers={via_device}, config_entry_id=config_entry_id
                )
                or self._first_device_in_domain(
                    self._devices.get_entries(identifiers={via_device}),
                    config_entry.domain,
                )
                or self._devices.get_entry(identifiers={via_device})
            )
            if via is None:
                report_usage(
                    "calls `device_registry.async_get_or_create` referencing a "
                    f"non existing `via_device` {via_device}, "
                    f"with device info: {device_info}",
                    core_behavior=ReportBehavior.LOG,
                    breaks_in_ha_version="2025.12.0",
                )
                via_device_id = UNDEFINED
            elif via.id == device.id:
                # A device can not be its own via device. Ignore the self-reference;
                # this will raise in HA Core 2027.8.
                report_usage(
                    "calls `device_registry.async_get_or_create` with a `via_device` "
                    "referencing the device itself; the via device is ignored",
                    core_behavior=ReportBehavior.LOG,
                    breaks_in_ha_version="2027.8.0",
                )
                via_device_id = UNDEFINED
            else:
                via_device_id = via.id
        elif via_device is None:
            # An explicit `via_device=None` means "no via device" (a via_device_id
            # alongside it is rejected above).
            via_device_id = None

        # On the owning integration's first re-registration of a device created by
        # splitting a pre-migration composite device, replace the identifiers and
        # connections copied from the composite with the ones the integration provides,
        # instead of merging. This block and the has_composite_identifiers flag
        # can be removed in HA Core 2027.8.
        identifiers_connections: dict[str, Any]
        has_composite_identifiers: bool | UndefinedType = UNDEFINED
        if device.has_composite_identifiers:
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
            disabled_by=disabled_by,
            entry_type=entry_type,
            is_new=is_new,
            name=name,
            has_composite_identifiers=has_composite_identifiers,
            new_config_subentry_id=config_subentry_id,
            suggested_area=suggested_area,
            via_device_id=via_device_id,
            **identifiers_connections,
            **validated_fields,
        )

        # This is safe because _async_update_device will always return a device
        # in this use case.
        assert device
        self._live_device_ids.setdefault(device.config_entry_id, set()).add(device.id)
        return device

    @callback
    def _resolve_translated_name(
        self,
        config_entry: ConfigEntry,
        translation_key: str,
        translation_placeholders: Mapping[str, str] | None,
    ) -> str:
        """Resolve a device's translated name from its translation key."""
        full_translation_key = (
            f"component.{config_entry.domain}.device.{translation_key}.name"
        )
        translations = translation.async_get_cached_translations(
            self.hass, self.hass.config.language, "device", config_entry.domain
        )
        translated_name = translations.get(full_translation_key, translation_key)
        return self._substitute_name_placeholders(
            config_entry.domain, translated_name, translation_placeholders or {}
        )

    @callback
    def async_get_or_create_child(
        self,
        *,
        config_entry_id: str,
        config_subentry_id: str | UndefinedType | None = UNDEFINED,
        disabled_by: DeviceEntryDisabler | UndefinedType | None = UNDEFINED,
        identifiers: set[tuple[str, str]],
        name: str | UndefinedType | None = UNDEFINED,
        parent_device_id: str,
        suggested_area: str | UndefinedType | None = UNDEFINED,
        translation_key: str | None = None,
        translation_placeholders: Mapping[str, str] | None = None,
    ) -> ChildDeviceEntry:
        """Get child device. Create if it doesn't exist.

        If identifiers match those of an existing device, that device is converted to
        a child device, preserving its id.
        """
        config_entry = self.hass.config_entries.async_get_entry(config_entry_id)
        if config_entry is None:
            raise HomeAssistantError(
                f"Can't link device to unknown config entry {config_entry_id}"
            )

        if (
            config_subentry_id is not UNDEFINED
            and config_subentry_id is not None
            and config_subentry_id not in config_entry.subentries
        ):
            raise HomeAssistantError(
                f"Config entry {config_entry_id} has no subentry {config_subentry_id}"
            )

        if translation_key:
            name = self._resolve_translated_name(
                config_entry, translation_key, translation_placeholders
            )

        # Reconstruct a ChildDeviceInfo dict from the arguments, used for error reporting
        # and conversion of an existing device to a child device.
        device_info: DeviceInfo = {  # type: ignore[assignment]
            key: val
            for key, val in (
                ("identifiers", identifiers),
                ("name", name),
                ("parent_device_id", parent_device_id),
                ("suggested_area", suggested_area),
            )
            if val is not UNDEFINED
        }

        domain = config_entry.domain

        if not identifiers:
            raise DeviceInfoError(
                domain,
                device_info,
                "a child device must have at least one identifier",
            )

        parent = self._device_data.get(parent_device_id)
        if parent is None:
            if parent_device_id in self._child_device_data:
                raise DeviceInfoError(
                    domain,
                    device_info,
                    f"parent_device_id {parent_device_id} is a child device; a "
                    "child device can't be the parent of another child device",
                )
            raise DeviceInfoError(
                domain,
                device_info,
                f"parent_device_id {parent_device_id} is not a registered device "
                "id; the parent device must be created before its child devices",
            )
        if parent.config_entry_id != config_entry_id:
            raise DeviceInfoError(
                domain,
                device_info,
                "a child device must belong to the same config entry as its "
                f"parent device {parent.id}",
            )

        # Interpret not specifying a subentry as None
        effective_config_subentry_id = (
            config_subentry_id if config_subentry_id is not UNDEFINED else None
        )
        if effective_config_subentry_id != parent.config_subentry_id:
            raise DeviceInfoError(
                domain,
                device_info,
                "a child device must belong to the same config subentry as its "
                f"parent device {parent.id}",
            )

        child_device = self._child_devices.get_entry(
            identifiers=identifiers, config_entry_id=config_entry_id
        )

        # Identifiers are unique per config entry, so raise if identifiers are
        # owned by another child device.
        for identifier in sorted(identifiers):
            if (
                other_child := self._child_devices.get_entry(
                    identifiers={identifier}, config_entry_id=config_entry_id
                )
            ) is not None and (
                child_device is None or other_child.id != child_device.id
            ):
                raise DeviceInfoError(
                    domain,
                    device_info,
                    f"identifier {identifier} is already registered for child "
                    f"device {other_child.id} of the same config entry",
                )

        if child_device is not None and child_device.parent_device_id != parent.id:
            raise DeviceInfoError(
                domain,
                device_info,
                "the child device is already registered with a different parent "
                f"device {child_device.parent_device_id}; reparenting is not "
                "supported, remove the child device first",
            )

        matched_device: DeviceEntry | None = None
        if child_device is None:
            matched_device = self._devices.get_entry(
                identifiers=identifiers, config_entry_id=config_entry_id
            )

        # Validate the device -> child conversion before the collision reconciliation
        # below, whose stale-duplicate strips would otherwise be left applied by a later
        # raise.
        if matched_device is not None:
            self._async_validate_device_to_child_conversion(
                matched_device, parent, config_entry, device_info
            )

        self._async_reconcile_collisions(
            matched_device,
            config_entry,
            device_info,
            identifiers,
            set(),
        )
        if child_device is None and matched_device is not None:
            # The identifiers are registered by a full device of the config entry:
            # the integration split the device into child devices, so convert it,
            # preserving its id.
            matched_device = self._devices[matched_device.id]
            child_device = self._async_convert_device_to_child(
                matched_device, parent, identifiers
            )

        is_new = False

        if child_device is None:
            is_new = True

            deleted_device = self._deleted_devices.get_entry(
                identifiers=identifiers,
                config_entry_id=config_entry_id,
            )
            if deleted_device is None:
                # Fall back to an orphan (its owning config entry was removed), as
                # for a full device
                deleted_device = self._deleted_devices.get_orphaned_entry(
                    identifiers, None, domain
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
                child_device = ChildDeviceEntry(
                    area_id=area_id,
                    config_entry_id=config_entry_id,
                    config_subentry_id=effective_config_subentry_id,
                    parent_device_id=parent.id,
                )
            else:
                self._deleted_devices.pop(deleted_device.id)
                child_device = deleted_device.to_child_device_entry(
                    config_entry,
                    effective_config_subentry_id,
                    identifiers,
                    disabled_by,
                    parent,
                )
                disabled_by = UNDEFINED

            self._child_devices[child_device.id] = child_device

        self._async_purge_colliding_deleted_devices(child_device, identifiers, set())

        updated_child_device = self._async_update_child_device(
            child_device.id,
            disabled_by=disabled_by,
            is_new=is_new,
            merge_identifiers=identifiers,
            name=name,
        )

        # This is safe because _async_update_child_device will always return a child
        # device in this use case.
        assert updated_child_device
        self._live_device_ids.setdefault(config_entry_id, set()).add(
            updated_child_device.id
        )
        return updated_child_device

    @callback
    def _async_validate_device_to_child_conversion(
        self,
        device: DeviceEntry,
        parent: DeviceEntry,
        config_entry: ConfigEntry,
        device_info: DeviceInfo,
    ) -> None:
        """Validate converting a device to a child device.

        Run before any mutation so a rejected conversion leaves the registry
        untouched.
        """
        if device.id == parent.id:
            raise DeviceInfoError(
                config_entry.domain, device_info, "a device can't be its own parent"
            )
        if self._child_devices.get_children_for_device_id(device.id):
            raise DeviceInfoError(
                config_entry.domain,
                device_info,
                f"can't convert device {device.id} to a child device: it has child "
                "devices itself, and a child device can't be the parent of another "
                "child device",
            )
        # The caller guarantees device and parent share the config entry; only
        # subentry agreement is left to check
        if device.config_subentry_id != parent.config_subentry_id:
            raise DeviceInfoError(
                config_entry.domain,
                device_info,
                "a child device must belong to the same config subentry as its "
                f"parent device {parent.id}",
            )
        if device.id in self._live_device_ids.get(device.config_entry_id, ()):
            raise DeviceInfoError(
                config_entry.domain,
                device_info,
                "identifiers registered as a device and as a child device by the "
                "same config entry",
            )

    @callback
    def _async_convert_device_to_child(
        self,
        device: DeviceEntry,
        parent: DeviceEntry,
        identifiers: set[tuple[str, str]],
    ) -> ChildDeviceEntry:
        """Convert a device to a child device, preserving its id.

        Lets an integration that already splits its devices (linking them with
        via_device) adopt child devices with no device id changes.

        The caller must have validated the conversion with
        _async_validate_device_to_child_conversion.
        """
        self.hass.verify_event_loop_thread("device_registry.async_get_or_create_child")

        # The update event reports the old values of every conceptually changed
        # field: the fields a child device does not have change to None / empty.
        changes: dict[str, Any] = {"parent_device_id": None}
        for field_name in (
            "configuration_url",
            "entry_type",
            "hw_version",
            "manufacturer",
            "model",
            "model_id",
            "serial_number",
            "sw_version",
            "via_device_id",
        ):
            if (old_value := getattr(device, field_name)) is not None:
                changes[field_name] = old_value
        if device.connections:
            changes["connections"] = device.connections
        # Replace identifiers copied from a pre-migration composite instead of
        # merging, as async_get_or_create does. Can be simplified in HA Core 2027.8.
        if device.has_composite_identifiers:
            new_identifiers = identifiers
        else:
            new_identifiers = device.identifiers | identifiers
        if new_identifiers != device.identifiers:
            changes["identifiers"] = device.identifiers

        disabled_by = device.disabled_by
        if disabled_by is None and parent.disabled:
            disabled_by = DeviceEntryDisabler.DEVICE
        if disabled_by != device.disabled_by:
            changes["disabled_by"] = device.disabled_by

        # A ChildDeviceEntry carries no composite_device_id, so a device split from a
        # pre-migration composite loses that membership here: an action targeting the
        # old composite id no longer reaches this split. Edge case that no longer
        # applies after the composite-device removal in HA Core 2027.8.
        child_device = ChildDeviceEntry(
            area_id=device.area_id,
            config_entry_id=device.config_entry_id,
            config_subentry_id=device.config_subentry_id,
            created_at=device.created_at,
            disabled_by=disabled_by,
            id=device.id,
            identifiers=new_identifiers,  # type: ignore[arg-type]
            labels=device.labels,  # type: ignore[arg-type]
            name=device.name,
            name_by_user=device.name_by_user,
            parent_device_id=parent.id,
        )
        del self._devices[device.id]
        self._child_devices[child_device.id] = child_device

        # A via_device_id must not resolve to a child device; detach inbound via
        # links to the converted device, as async_remove_device does, before firing
        # the conversion event.
        for other_device in list(self._devices.values()):
            if other_device.via_device_id == device.id:
                self._async_update_device(other_device.id, via_device_id=None)

        self.async_schedule_save()
        self.hass.bus.async_fire_internal(
            EVENT_DEVICE_REGISTRY_UPDATED,
            _EventDeviceRegistryUpdatedData_Update(
                action="update", device_id=child_device.id, changes=changes
            ),
        )
        return child_device

    @callback
    def _async_update_device(  # noqa: C901
        self,
        device_id: str,
        *,
        add_config_entry_id: str | UndefinedType = UNDEFINED,
        add_config_subentry_id: str | UndefinedType | None = UNDEFINED,
        # Only set when stripping colliding keys from a stale device: its retained
        # keys can still be duplicated in other stale devices and must not validate.
        allow_collisions: bool = False,
        area_id: str | UndefinedType | None = UNDEFINED,
        configuration_url: str | URL | UndefinedType | None = UNDEFINED,
        disabled_by: DeviceEntryDisabler | UndefinedType | None = UNDEFINED,
        entry_type: DeviceEntryType | UndefinedType | None = UNDEFINED,
        hw_version: str | UndefinedType | None = UNDEFINED,
        is_new: bool = False,
        labels: set[str] | UndefinedType = UNDEFINED,
        manufacturer: str | UndefinedType | None = UNDEFINED,
        merge_connections: set[tuple[str, str]] | UndefinedType = UNDEFINED,
        merge_identifiers: set[tuple[str, str]] | UndefinedType = UNDEFINED,
        model: str | UndefinedType | None = UNDEFINED,
        model_id: str | UndefinedType | None = UNDEFINED,
        name_by_user: str | UndefinedType | None = UNDEFINED,
        name: str | UndefinedType | None = UNDEFINED,
        # has_composite_identifiers can be removed in HA Core 2027.8
        has_composite_identifiers: bool | UndefinedType = UNDEFINED,
        new_config_entry_id: str | UndefinedType = UNDEFINED,
        new_config_subentry_id: str | UndefinedType | None = UNDEFINED,
        new_connections: set[tuple[str, str]] | UndefinedType = UNDEFINED,
        new_identifiers: set[tuple[str, str]] | UndefinedType = UNDEFINED,
        remove_config_entry_id: str | UndefinedType = UNDEFINED,
        remove_config_subentry_id: str | UndefinedType | None = UNDEFINED,
        serial_number: str | UndefinedType | None = UNDEFINED,
        # Can be removed when suggested_area is removed from DeviceEntry
        suggested_area: str | UndefinedType | None = UNDEFINED,
        sw_version: str | UndefinedType | None = UNDEFINED,
        via_device_id: str | UndefinedType | None = UNDEFINED,
    ) -> DeviceEntry | None:
        """Private update device attributes.

        :param add_config_subentry_id: Add the device to a specific
            subentry of add_config_entry_id
        :param remove_config_subentry_id: Remove the device from a
            specific subentry of remove_config_entry_id
        """
        old = self._devices[device_id]

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

        if (
            via_device_id is not UNDEFINED
            and via_device_id is not None
            and self.async_get(via_device_id, include_child_devices=False) is None
        ):
            if via_device_id in self._child_device_data:
                raise HomeAssistantError(
                    f"via_device_id {via_device_id} is a child device, which "
                    "can't be a via device"
                )
            raise HomeAssistantError(
                f"Can't link device to unknown via device {via_device_id}"
            )

        if via_device_id == device_id:
            raise HomeAssistantError("A device can not be its own via device")

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
        target_config_subentry_id: str | UndefinedType | None = UNDEFINED
        pending_move: _PendingMove | UndefinedType | None = UNDEFINED
        if new_config_entry_id is not UNDEFINED:
            target_config_entry_id = new_config_entry_id
            target_config_subentry_id = (
                new_config_subentry_id
                if new_config_subentry_id is not UNDEFINED
                else None
            )
            # An immediate move to a new config entry supersedes a deferred move from an
            # earlier add_config_entry_id; clear it so a later removal of the new owner
            # deletes the device instead of performing the stale move.
            pending_move = None
        elif new_config_subentry_id is not UNDEFINED:
            target_config_subentry_id = new_config_subentry_id
        else:
            if add_config_entry_id is not UNDEFINED:
                # Adding the config entry (and subentry) the device already belongs to is a
                # no-op; recording it as a pending move would make a later removal of that
                # sole owner move the device to itself instead of deleting it.
                already_owner = add_config_entry_id == old.config_entry_id and (
                    add_config_subentry_id is UNDEFINED
                    or add_config_subentry_id == old.config_subentry_id
                )
                if not already_owner:
                    pending_move = _PendingMove(
                        add_config_entry_id,
                        add_config_subentry_id
                        if add_config_subentry_id is not UNDEFINED
                        else None,
                        _current_integration_domain(),
                    )
            if remove_config_entry_id == old.config_entry_id and (
                remove_config_subentry_id is UNDEFINED
                or remove_config_subentry_id == old.config_subentry_id
            ):
                move_from_prior_call = pending_move is UNDEFINED
                move_target = (
                    pending_move if pending_move is not UNDEFINED else old._pending_move  # noqa: SLF001
                )
                # A deferred move armed by an earlier add_config_entry_id only completes
                # if the integration now removing the owning entry is the one that armed
                # it. A removal from a different integration (e.g. device_tracker
                # attaching a shared MAC) is unrelated, so cancel the move and delete the
                # device instead of silently transferring it. Origins from core/tests are
                # undetermined (None) and never cancel.
                if (
                    move_target is not None
                    and move_from_prior_call
                    and move_target.origin_domain is not None
                    and (current_domain := _current_integration_domain()) is not None
                    and current_domain != move_target.origin_domain
                ):
                    move_target = None
                if move_target is None:
                    # A composite via_device_id resolves to the split owned by the
                    # entry being removed, i.e. this device, so it is a self-reference;
                    # reject it before deleting, atomically like the direct-id check
                    # before the ownership changes above.
                    if (
                        via_device_id is not UNDEFINED
                        and via_device_id is not None
                        and via_device_id == old.composite_device_id
                    ):
                        raise HomeAssistantError(
                            "A device can not be its own via device"
                        )
                    self.async_remove_device(device_id)
                    return None
                target_config_entry_id = move_target.config_entry_id
                target_config_subentry_id = move_target.config_subentry_id
                pending_move = None
                # A parent with child devices can't move (enforced again below); reject
                # here before mutating the runtime-only sibling pending moves, so the
                # rejected move leaves no partial state behind.
                if self._child_devices.get_children_for_device_id(device_id):
                    raise HomeAssistantError(
                        f"Can't move device {device_id}: it has child devices"
                    )
                # A pre-migration composite's splits share identity, so once one split
                # completes the move to the target entry the others must not also move
                # there and collide; clear their pending moves.
                if old.composite_device_id is not None:
                    for sibling in self._devices.get_devices_for_composite_device_id(
                        old.composite_device_id
                    ):
                        if (
                            sibling.id != device_id
                            and sibling._pending_move is not None  # noqa: SLF001
                        ):
                            self._devices[sibling.id] = attr.evolve(
                                sibling, pending_move=None
                            )

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

        # The config entry owning the device after the update. Identifiers and
        # connections are unique per config entry, so they are validated against the
        # owning entry, as is the disabled state.
        effective_config_entry_id = (
            target_config_entry_id
            if target_config_entry_id is not UNDEFINED
            else old.config_entry_id
        )
        is_move = effective_config_entry_id != old.config_entry_id

        # A child device lives on the same config entry and subentry as its parent, so
        # a parent with child devices can't move without cascading moves, which are not
        # supported.
        if (
            is_move or "config_subentry_id" in new_values
        ) and self._child_devices.get_children_for_device_id(device_id):
            raise HomeAssistantError(
                f"Can't move device {device_id}: it has child devices"
            )

        if via_device_id is not UNDEFINED and via_device_id is not None:
            # Existence was already validated, so this cannot be None
            via_device_id = self._resolve_via_device_id(
                via_device_id, effective_config_entry_id
            )
            # Direct self-references were rejected before the ownership changes above;
            # this catches a composite via_device_id that resolves to device_id.
            if via_device_id == device_id:
                raise HomeAssistantError("A device can not be its own via device")

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
                device_id, effective_config_entry_id, new_connections, allow_collisions
            )
            old_values["connections"] = old.connections

        if new_identifiers is not UNDEFINED:
            added_identifiers = new_values["identifiers"] = self._validate_identifiers(
                device_id, effective_config_entry_id, new_identifiers, allow_collisions
            )
            old_values["identifiers"] = old.identifiers

        # On a move to another config entry, validate the identifiers and connections
        # retained from the old entry against the new one, so the move can't silently
        # overwrite the index slot of a device that already has the same identity there.
        # A full new_identifiers / new_connections replacement is validated above;
        # merge_* only adds, so the retained old values still need checking here.
        if is_move:
            if new_identifiers is UNDEFINED:
                self._validate_identifiers(
                    device_id, effective_config_entry_id, old.identifiers, False
                )
            if new_connections is UNDEFINED:
                self._validate_connections(
                    device_id, effective_config_entry_id, old.connections, False
                )

        # An explicit disabled_by must be consistent with the disabled state of the
        # config entry owning the device after the update: a device can't be enabled
        # when the owning config entry is disabled, and can't be disabled by
        # CONFIG_ENTRY when the owning config entry is enabled. An inconsistent
        # disabled_by is ignored; this will raise in HA Core 2027.8.
        # On a move, reflect the new owning config entry's disabled state (as restoring
        # a deleted device does) unless a consistent disabled_by was passed explicitly:
        # disable an enabled device moved onto a disabled entry, and clear a
        # CONFIG_ENTRY disable when moved onto an enabled entry. A USER disable is
        # preserved. Disable_by of a new device is handled the same way, so a create
        # can't leave the device's disabled state contradicting the owning entry's.
        if (disabled_by is not UNDEFINED or is_move or is_new) and (
            owning_entry := self.hass.config_entries.async_get_entry(
                effective_config_entry_id
            )
        ) is not None:
            if is_move:
                context = "when moving a device to"
            elif is_new:
                context = "when creating a device attached to"
            else:
                context = "on a device belonging to"
            if disabled_by is None and owning_entry.disabled_by:
                report_usage(
                    f"sets disabled_by to None {context} the disabled "
                    f"config entry {effective_config_entry_id}",
                    core_behavior=ReportBehavior.LOG,
                    breaks_in_ha_version="2027.8",
                )
                disabled_by = UNDEFINED
            elif (
                disabled_by is DeviceEntryDisabler.CONFIG_ENTRY
                and not owning_entry.disabled_by
            ):
                report_usage(
                    f"sets disabled_by to DeviceEntryDisabler.CONFIG_ENTRY {context} "
                    f"the enabled config entry {effective_config_entry_id}",
                    core_behavior=ReportBehavior.LOG,
                    breaks_in_ha_version="2027.8",
                )
                disabled_by = UNDEFINED
            if (is_move or is_new) and disabled_by is UNDEFINED:
                if owning_entry.disabled_by:
                    if old.disabled_by is None:
                        disabled_by = DeviceEntryDisabler.CONFIG_ENTRY
                elif old.disabled_by is DeviceEntryDisabler.CONFIG_ENTRY:
                    disabled_by = None

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
        self._devices[device_id] = new

        # On a move, the device's whole retained identity newly appears in the target
        # config entry; added_identifiers/added_connections are empty on a retained-
        # identity move, so match the target entry's deleted device by the full identity.
        match_identifiers: set[tuple[str, str]] | None
        match_connections: set[tuple[str, str]] | None
        if is_move:
            match_identifiers = new.identifiers
            match_connections = new.connections
        else:
            match_identifiers = added_identifiers
            match_connections = added_connections
        # A deleted device holding an identity the device now owns can never restore
        for deleted_device_id in self._deleted_devices.get_colliding_device_ids(
            match_identifiers or set(),
            match_connections or set(),
            config_entry_id=effective_config_entry_id,
            exclude_device_id=None,
        ):
            del self._deleted_devices[deleted_device_id]

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

        # Disabling a parent device disables its child devices; enabling it enables
        # the child devices it disabled. CONFIG_ENTRY transitions are skipped: they
        # are applied to parents and children alike by
        # async_config_entry_disabled_by_changed, which iterates all the config
        # entry's devices.
        if "disabled_by" in old_values and (
            children := self._child_devices.get_children_for_device_id(device_id)
        ):
            if new.disabled_by is None:
                for child in children:
                    if child.disabled_by is DeviceEntryDisabler.DEVICE:
                        self._async_update_child_device(child.id, disabled_by=None)
            elif new.disabled_by is not DeviceEntryDisabler.CONFIG_ENTRY:
                for child in children:
                    if not child.disabled:
                        self._async_update_child_device(
                            child.id, disabled_by=DeviceEntryDisabler.DEVICE
                        )

        return new

    @callback
    def _async_update_child_device(
        self,
        child_device_id: str,
        *,
        area_id: str | UndefinedType | None = UNDEFINED,
        disabled_by: DeviceEntryDisabler | UndefinedType | None = UNDEFINED,
        is_new: bool = False,
        labels: set[str] | UndefinedType = UNDEFINED,
        merge_identifiers: set[tuple[str, str]] | UndefinedType = UNDEFINED,
        name_by_user: str | UndefinedType | None = UNDEFINED,
        name: str | UndefinedType | None = UNDEFINED,
        new_identifiers: set[tuple[str, str]] | UndefinedType = UNDEFINED,
    ) -> ChildDeviceEntry | None:
        """Private update child device attributes."""
        old = self._child_devices[child_device_id]

        new_values: dict[str, Any] = {}  # Dict with new key/value pairs
        old_values: dict[str, Any] = {}  # Dict with old key/value pairs

        if merge_identifiers is not UNDEFINED and new_identifiers is not UNDEFINED:
            raise HomeAssistantError(
                "Cannot define both merge_identifiers and new_identifiers"
            )

        if new_identifiers is not UNDEFINED and not new_identifiers:
            raise HomeAssistantError("A child device must have at least one identifier")

        added_identifiers: set[tuple[str, str]] | None = None

        if merge_identifiers is not UNDEFINED:
            merge_identifiers = self._validate_child_identifiers(
                child_device_id,
                old.config_entry_id,
                merge_identifiers,
            )
            old_identifiers = old.identifiers
            if not merge_identifiers.issubset(old_identifiers):
                added_identifiers = merge_identifiers
                new_values["identifiers"] = old_identifiers | merge_identifiers
                old_values["identifiers"] = old_identifiers

        elif new_identifiers is not UNDEFINED:
            added_identifiers = new_values["identifiers"] = (
                self._validate_child_identifiers(
                    child_device_id,
                    old.config_entry_id,
                    new_identifiers,
                )
            )
            old_values["identifiers"] = old.identifiers

        # An explicit disabled_by must be consistent with the disabled state of the
        # owning config entry (as for a full device) and of the parent device: a child
        # of a disabled parent can't be enabled, and can't be disabled by DEVICE when
        # the parent is enabled.
        if disabled_by is not UNDEFINED or is_new:
            parent_device = self._device_data[old.parent_device_id]
            owning_entry = self.hass.config_entries.async_get_entry(old.config_entry_id)
            context = (
                "when creating a child device attached to"
                if is_new
                else "on a child device belonging to"
            )
            parent_context = (
                "when creating a child device whose parent device is"
                if is_new
                else "on a child device whose parent device is"
            )
            if owning_entry is not None:
                if disabled_by is None and owning_entry.disabled_by:
                    report_usage(
                        f"sets disabled_by to None {context} the disabled "
                        f"config entry {old.config_entry_id}",
                        core_behavior=ReportBehavior.LOG,
                        breaks_in_ha_version="2027.8",
                    )
                    disabled_by = UNDEFINED
                elif (
                    disabled_by is DeviceEntryDisabler.CONFIG_ENTRY
                    and not owning_entry.disabled_by
                ):
                    report_usage(
                        f"sets disabled_by to DeviceEntryDisabler.CONFIG_ENTRY "
                        f"{context} the enabled config entry {old.config_entry_id}",
                        core_behavior=ReportBehavior.LOG,
                        breaks_in_ha_version="2027.8",
                    )
                    disabled_by = UNDEFINED
                if is_new and disabled_by is UNDEFINED:
                    if owning_entry.disabled_by:
                        if old.disabled_by is None:
                            disabled_by = DeviceEntryDisabler.CONFIG_ENTRY
                    elif old.disabled_by is DeviceEntryDisabler.CONFIG_ENTRY:
                        disabled_by = None
            if disabled_by is DeviceEntryDisabler.DEVICE and not parent_device.disabled:
                report_usage(
                    f"sets disabled_by to DeviceEntryDisabler.DEVICE "
                    f"{parent_context} enabled",
                    core_behavior=ReportBehavior.LOG,
                    breaks_in_ha_version="2027.8",
                )
                disabled_by = UNDEFINED
            # Report an external attempt to enable a child whose parent stays disabled.
            if (
                disabled_by is None
                and parent_device.disabled
                and old.disabled_by is not DeviceEntryDisabler.CONFIG_ENTRY
            ):
                report_usage(
                    f"sets disabled_by to None {parent_context} disabled",
                    core_behavior=ReportBehavior.LOG,
                    breaks_in_ha_version="2027.8",
                )
            # Coerce the child back to a parent-derived DEVICE disable, keeping it
            # consistent with its disabled parent.
            if parent_device.disabled and (
                disabled_by is None
                or (is_new and disabled_by is UNDEFINED and old.disabled_by is None)
            ):
                disabled_by = DeviceEntryDisabler.DEVICE

        for attr_name, value in (
            ("area_id", area_id),
            ("disabled_by", disabled_by),
            ("labels", labels),
            ("name", name),
            ("name_by_user", name_by_user),
        ):
            if value is not UNDEFINED and value != getattr(old, attr_name):
                new_values[attr_name] = value
                old_values[attr_name] = getattr(old, attr_name)

        if not new_values and not is_new:
            return old

        new_values["modified_at"] = utcnow()

        self.hass.verify_event_loop_thread("device_registry._async_update_child_device")
        new = attr.evolve(old, **new_values)
        self._child_devices[child_device_id] = new

        # A deleted device holding an identity the child device now owns can never
        # restore
        for deleted_device_id in self._deleted_devices.get_colliding_device_ids(
            added_identifiers or set(),
            set(),
            config_entry_id=old.config_entry_id,
            exclude_device_id=None,
        ):
            del self._deleted_devices[deleted_device_id]

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
        add_config_subentry_id: str | UndefinedType | None = UNDEFINED,
        area_id: str | UndefinedType | None = UNDEFINED,
        configuration_url: str | URL | UndefinedType | None = UNDEFINED,
        disabled_by: DeviceEntryDisabler | UndefinedType | None = UNDEFINED,
        entry_type: DeviceEntryType | UndefinedType | None = UNDEFINED,
        hw_version: str | UndefinedType | None = UNDEFINED,
        labels: set[str] | UndefinedType = UNDEFINED,
        manufacturer: str | UndefinedType | None = UNDEFINED,
        merge_connections: set[tuple[str, str]] | UndefinedType = UNDEFINED,
        merge_identifiers: set[tuple[str, str]] | UndefinedType = UNDEFINED,
        model: str | UndefinedType | None = UNDEFINED,
        model_id: str | UndefinedType | None = UNDEFINED,
        name_by_user: str | UndefinedType | None = UNDEFINED,
        name: str | UndefinedType | None = UNDEFINED,
        new_config_entry_id: str | UndefinedType = UNDEFINED,
        new_config_subentry_id: str | UndefinedType | None = UNDEFINED,
        new_connections: set[tuple[str, str]] | UndefinedType = UNDEFINED,
        new_identifiers: set[tuple[str, str]] | UndefinedType = UNDEFINED,
        remove_config_entry_id: str | UndefinedType = UNDEFINED,
        remove_config_subentry_id: str | UndefinedType | None = UNDEFINED,
        serial_number: str | UndefinedType | None = UNDEFINED,
        # suggested_area is deprecated and will be removed in 2026.9
        suggested_area: str | UndefinedType | None = UNDEFINED,
        sw_version: str | UndefinedType | None = UNDEFINED,
        via_device_id: str | UndefinedType | None = UNDEFINED,
    ) -> DeviceEntry | None:
        """Update device attributes.

        This updates a main device. To update a child device, use
        async_update_child_device.

        A device belongs to a single config entry and subentry. To move a device to
        another config entry or subentry, pass new_config_entry_id and/or
        new_config_subentry_id. To remove a device, call async_remove_device.

        :param add_config_entry_id: Deprecated. Combined with remove_config_entry_id it
            moves the device; on its own it does nothing. Use new_config_entry_id
            instead.
        :param add_config_subentry_id: Deprecated. Combined with remove_config_subentry_id
            it moves the device to another subentry; on its own it does nothing. Use
            new_config_subentry_id instead.
        :param disabled_by: Disable or enable the device. Must be consistent with the
            disabled state of the config entry owning the device after the update:
            a device can't be enabled when the owning config entry is disabled, and
            can't be disabled by CONFIG_ENTRY when the owning config entry is enabled.
            An inconsistent disabled_by is deprecated and ignored; this will raise in
            HA Core 2027.8.
        :param merge_connections: Deprecated. Adds connections to the device, keeping the
            ones it already has. Pass the full set of connections as new_connections
            instead.
        :param merge_identifiers: Deprecated. Adds identifiers to the device, keeping the
            ones it already has. Pass the full set of identifiers as new_identifiers
            instead.
        :param new_config_entry_id: Move the device to this config entry. Unless a
            disabled_by consistent with the new config entry's disabled state is
            passed explicitly, the device's disabled state is updated to reflect the
            new config entry's disabled state.
        :param new_config_subentry_id: Move the device to this subentry.
        :param remove_config_entry_id: Deprecated. Remove the device if it is the
            device's config entry, unless combined with add_config_entry_id to move the
            device. Use new_config_entry_id to move, or async_remove_device to remove.
        :param remove_config_subentry_id: Deprecated. Remove the device from a specific
            subentry of remove_config_entry_id. Use new_config_subentry_id to move, or
            async_remove_device to remove.
        """
        if device_id not in self._devices and device_id in self._child_devices:
            raise HomeAssistantError(
                f"Device {device_id} is a child device; use async_update_child_device"
            )
        if disabled_by is DeviceEntryDisabler.DEVICE:
            raise HomeAssistantError(
                "disabled_by=DeviceEntryDisabler.DEVICE is only valid for a child "
                "device"
            )
        if (
            underlying_ids := self._async_device_ids_for_composite_device_id(device_id)
        ) is not None:
            # Fan the update out to each underlying device; keep in sync with the
            # update parameters above.
            update_args = {
                "add_config_entry_id": add_config_entry_id,
                "add_config_subentry_id": add_config_subentry_id,
                "area_id": area_id,
                "configuration_url": configuration_url,
                "disabled_by": disabled_by,
                "entry_type": entry_type,
                "hw_version": hw_version,
                "labels": labels,
                "manufacturer": manufacturer,
                "merge_connections": merge_connections,
                "merge_identifiers": merge_identifiers,
                "model": model,
                "model_id": model_id,
                "name_by_user": name_by_user,
                "name": name,
                "new_config_entry_id": new_config_entry_id,
                "new_config_subentry_id": new_config_subentry_id,
                "new_connections": new_connections,
                "new_identifiers": new_identifiers,
                "remove_config_entry_id": remove_config_entry_id,
                "remove_config_subentry_id": remove_config_subentry_id,
                "serial_number": serial_number,
                "suggested_area": suggested_area,
                "sw_version": sw_version,
                "via_device_id": via_device_id,
            }
            return self._async_update_composite_device(
                device_id, underlying_ids, update_args
            )
        if (
            add_config_entry_id is not UNDEFINED
            or add_config_subentry_id is not UNDEFINED
            or remove_config_entry_id is not UNDEFINED
            or remove_config_subentry_id is not UNDEFINED
        ):
            report_usage(
                "calls `device_registry.async_update_device` with one of "
                "`add_config_entry_id`, `add_config_subentry_id`, "
                "`remove_config_entry_id` or `remove_config_subentry_id`; a device now "
                "belongs to a single config entry and subentry. Move a device with "
                "`new_config_entry_id` and/or `new_config_subentry_id`, or remove it "
                "with `async_remove_device`",
                core_behavior=ReportBehavior.ERROR,
                core_integration_behavior=ReportBehavior.ERROR,
                breaks_in_ha_version="2027.8.0",
            )
        if suggested_area is not UNDEFINED:
            report_usage(
                "passes a suggested_area to device_registry.async_update device",
                core_behavior=ReportBehavior.LOG,
                breaks_in_ha_version="2026.9.0",
            )
        if merge_connections is not UNDEFINED or merge_identifiers is not UNDEFINED:
            report_usage(
                "calls `device_registry.async_update_device` with `merge_connections` "
                "or `merge_identifiers`; these only add to the device's existing "
                "connections or identifiers. Pass the full set as `new_connections` or "
                "`new_identifiers` instead",
                core_behavior=ReportBehavior.ERROR,
                core_integration_behavior=ReportBehavior.ERROR,
                breaks_in_ha_version="2027.9.0",
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
    def async_update_child_device(
        self,
        device_id: str,
        *,
        area_id: str | UndefinedType | None = UNDEFINED,
        disabled_by: DeviceEntryDisabler | UndefinedType | None = UNDEFINED,
        labels: set[str] | UndefinedType = UNDEFINED,
        name_by_user: str | UndefinedType | None = UNDEFINED,
        name: str | UndefinedType | None = UNDEFINED,
        new_identifiers: set[tuple[str, str]] | UndefinedType = UNDEFINED,
    ) -> ChildDeviceEntry:
        """Update child device attributes.

        :param disabled_by: Disable or enable the child device. Must be consistent with
            the disabled state of the config entry owning the child device and of its
            parent device: a child device can't be enabled when either is disabled. An
            inconsistent disabled_by is deprecated and ignored; this will raise in HA
            Core 2027.8.
        """
        if device_id not in self._child_devices and device_id in self._devices:
            raise HomeAssistantError(
                f"Device {device_id} is a main device; use async_update_device"
            )
        updated = self._async_update_child_device(
            device_id,
            area_id=area_id,
            disabled_by=disabled_by,
            labels=labels,
            name_by_user=name_by_user,
            name=name,
            new_identifiers=new_identifiers,
        )
        if TYPE_CHECKING:
            assert updated is not None
        return updated

    @callback
    def _async_reconcile_collisions(
        self,
        matched_device: DeviceEntry | None,
        config_entry: ConfigEntry,
        device_info: DeviceInfo,
        identifiers: set[tuple[str, str]],
        connections: set[tuple[str, str]],
    ) -> None:
        """Resolve device key collisions with the registering device.

        Shared keys are stripped from stale duplicates (devices not registered this
        setup session); a duplicate left without any keys is removed. A collision
        with a device registered this setup session raises.
        """
        matched_device_id: str | None = None
        if matched_device is not None:
            matched_device_id = matched_device.id
            if not matched_device.has_composite_identifiers:
                identifiers = matched_device.identifiers | identifiers
                connections = matched_device.connections | connections
        colliding = self._devices.get_colliding_device_ids(
            identifiers,
            connections,
            config_entry_id=config_entry.entry_id,
            exclude_device_id=matched_device_id,
        )
        live_device_ids = self._live_device_ids.get(config_entry.entry_id, ())
        for holder_id, (shared_identifiers, shared_connections) in colliding.items():
            if holder_id not in live_device_ids:
                continue
            raise DeviceInfoError(
                config_entry.domain,
                device_info,
                f"identifiers or connections "
                f"{sorted(shared_identifiers | shared_connections)} are already "
                f"registered for device {holder_id} of the same config entry",
            )
        for holder_id, (shared_identifiers, shared_connections) in colliding.items():
            holder = self._devices[holder_id]
            remaining_identifiers = holder.identifiers - shared_identifiers
            remaining_connections = holder.connections - shared_connections
            if not remaining_identifiers and not remaining_connections:
                _LOGGER.debug(
                    "Removing device %s, its identifiers and connections are all "
                    "registered by another device of the same config entry",
                    holder_id,
                )
                self.async_remove_device(holder_id)
                continue
            _LOGGER.debug(
                "Stripping %s from device %s, registered by another device of the "
                "same config entry",
                sorted(shared_identifiers | shared_connections),
                holder_id,
            )
            strip_values: dict[str, Any] = {}
            if shared_identifiers:
                strip_values["new_identifiers"] = remaining_identifiers
            if shared_connections:
                strip_values["new_connections"] = remaining_connections
            self._async_update_device(holder_id, allow_collisions=True, **strip_values)

    @callback
    def _async_purge_colliding_deleted_devices(
        self,
        device: AnyDeviceEntry,
        identifiers: set[tuple[str, str]],
        connections: set[tuple[str, str]],
    ) -> None:
        """Purge deleted devices with key collisions."""
        if isinstance(device, ChildDeviceEntry):
            identifiers = device.identifiers | identifiers
        elif not device.has_composite_identifiers:
            identifiers = device.identifiers | identifiers
            connections = device.connections | connections
        colliding = self._deleted_devices.get_colliding_device_ids(
            identifiers,
            connections,
            config_entry_id=device.config_entry_id,
            exclude_device_id=None,
        )
        if not colliding:
            return
        for deleted_device_id in colliding:
            _LOGGER.debug(
                "Removing deleted device %s, its identifiers or connections are "
                "registered by device %s of the same config entry",
                deleted_device_id,
                device.id,
            )
            del self._deleted_devices[deleted_device_id]
        self.async_schedule_save()

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
                existing_device := self._devices.get_entry(
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
                existing_device := self._devices.get_entry(
                    identifiers={identifier}, config_entry_id=config_entry_id
                )
            ) and existing_device.id != device_id:
                raise DeviceIdentifierCollisionError(identifiers, existing_device)
            if (
                existing_child_device := self._child_devices.get_entry(
                    identifiers={identifier}, config_entry_id=config_entry_id
                )
            ) is not None:
                raise DeviceIdentifierCollisionError(identifiers, existing_child_device)

        return identifiers

    @callback
    def _validate_child_identifiers(
        self,
        child_device_id: str,
        config_entry_id: str,
        identifiers: set[tuple[str, str]],
    ) -> set[tuple[str, str]]:
        """Validate child device identifiers, raise on collision.

        Identifiers are unique per config entry, in a namespace shared between
        devices and child devices.
        """
        for identifier in identifiers:
            if (
                existing_child_device := self._child_devices.get_entry(
                    identifiers={identifier}, config_entry_id=config_entry_id
                )
            ) and existing_child_device.id != child_device_id:
                raise DeviceIdentifierCollisionError(identifiers, existing_child_device)
            if (
                existing_device := self._devices.get_entry(
                    identifiers={identifier}, config_entry_id=config_entry_id
                )
            ) is not None:
                raise DeviceIdentifierCollisionError(identifiers, existing_device)

        return identifiers

    @callback
    def _async_update_composite_device(
        self,
        composite_id: str,
        underlying_ids: list[str],
        update_args: dict[str, Any],
    ) -> DeviceEntry | None:
        """Fan an async_update_device call on a composite out to its real devices."""
        forward = {
            name: value for name, value in update_args.items() if value is not UNDEFINED
        }
        if ignored := [
            name for name in _COMPOSITE_IGNORED_UPDATE_ARGS if name in forward
        ]:
            # These rewrite a device's functional identity or move it, which is ambiguous
            # across the composite's underlying devices; drop them rather than corrupt or
            # collide, and report the offending integration.
            report_usage(
                f"passed {', '.join(ignored)} to device_registry.async_update_device "
                "for a composite device that spans several config entries (returned for "
                "an ambiguous async_get_device lookup, or "
                "resolved from a stored device id of a pre-migration composite); the "
                "argument cannot be applied to the merged device and was ignored - "
                "target a single device, e.g. one returned by "
                "async_entries_for_config_entry",
                core_behavior=ReportBehavior.LOG,
            )
            for name in ignored:
                del forward[name]
        for underlying_id in underlying_ids:
            self.async_update_device(underlying_id, **forward)
        remaining = [
            self._devices[underlying_id]
            for underlying_id in underlying_ids
            if underlying_id in self._devices
        ]
        if not remaining:
            return None
        return self._restore_composite_device(composite_id, remaining)

    @callback
    def async_remove_device(self, device_id: str) -> None:
        """Remove a device or child device from the device registry."""
        if (child_device := self._child_device_data.get(device_id)) is not None:
            self._async_remove_child_device(child_device)
            return
        if (
            underlying_ids := self._async_device_ids_for_composite_device_id(device_id)
        ) is not None:
            for underlying_id in underlying_ids:
                self.async_remove_device(underlying_id)
            return
        self.hass.verify_event_loop_thread("device_registry.async_remove_device")
        # Removing the parent removes its child devices
        for child in self._child_devices.get_children_for_device_id(device_id):
            self._async_remove_child_device(child)
        device = self._devices.pop(device_id)
        config_entry = self.hass.config_entries.async_get_entry(device.config_entry_id)
        self._deleted_devices[device_id] = DeletedDeviceEntry(
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
            domain=config_entry.domain if config_entry is not None else None,
        )
        for other_device in list(self._devices.values()):
            if other_device.via_device_id == device_id:
                self._async_update_device(other_device.id, via_device_id=None)
        self.hass.bus.async_fire_internal(
            EVENT_DEVICE_REGISTRY_UPDATED,
            _EventDeviceRegistryUpdatedData_Remove(
                action="remove", device_id=device_id, device=device.dict_repr
            ),
        )
        self.async_schedule_save()

    @callback
    def _async_remove_child_device(self, child_device: ChildDeviceEntry) -> None:
        """Remove a child device from the device registry."""
        self.hass.verify_event_loop_thread("device_registry.async_remove_device")
        del self._child_devices[child_device.id]
        config_entry = self.hass.config_entries.async_get_entry(
            child_device.config_entry_id
        )
        self._deleted_devices[child_device.id] = DeletedDeviceEntry(
            area_id=child_device.area_id,
            config_entry_id=child_device.config_entry_id,
            config_subentry_id=child_device.config_subentry_id,
            connections=set(),
            created_at=child_device.created_at,
            disabled_by=child_device.disabled_by,
            identifiers=child_device.identifiers,
            id=child_device.id,
            labels=child_device.labels,
            modified_at=utcnow(),
            name_by_user=child_device.name_by_user,
            orphaned_timestamp=None,
            domain=config_entry.domain if config_entry is not None else None,
        )
        self.hass.bus.async_fire_internal(
            EVENT_DEVICE_REGISTRY_UPDATED,
            _EventDeviceRegistryUpdatedData_Remove(
                action="remove",
                device_id=child_device.id,
                device=child_device.dict_repr,
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
        child_devices = ChildDeviceRegistryItems()
        deleted_devices = DeletedDeviceRegistryItems()
        child_devices_dropped = False

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

            for child_device in data["child_devices"]:
                # The remove cascade makes a child without its parent impossible;
                # guard against a manually edited or corrupted store anyway.
                if (
                    parent_device_id := child_device["parent_device_id"]
                ) not in devices:
                    _LOGGER.error(
                        "Dropping child device %s: its parent device %s is not in "
                        "the device registry",
                        child_device["id"],
                        parent_device_id,
                    )
                    child_devices_dropped = True
                    continue
                child_devices[child_device["id"]] = ChildDeviceEntry(
                    area_id=child_device["area_id"],
                    config_entry_id=child_device["config_entry_id"],
                    config_subentry_id=child_device["config_subentry_id"],
                    created_at=datetime.fromisoformat(child_device["created_at"]),
                    disabled_by=(
                        DeviceEntryDisabler(child_device["disabled_by"])
                        if child_device["disabled_by"]
                        else None
                    ),
                    id=child_device["id"],
                    identifiers={
                        tuple(iden)  # type: ignore[misc]
                        for iden in child_device["identifiers"]
                    },
                    labels=set(child_device["labels"]),
                    modified_at=datetime.fromisoformat(child_device["modified_at"]),
                    name_by_user=child_device["name_by_user"],
                    name=child_device["name"],
                    parent_device_id=parent_device_id,
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
                    domain=device["domain"],
                )

        if (
            shadowed_count := devices.count_shadowed_keys()
            + deleted_devices.count_shadowed_keys()
        ):
            _LOGGER.info(
                "Loaded %d identifiers/connections registered to multiple devices of "
                "one config entry; they will be reconciled as integrations register "
                "their devices",
                shadowed_count,
            )

        self._devices = devices
        self.devices = _DeprecatedDeviceRegistryItemsView(self._devices)
        self._child_devices = child_devices
        self.child_devices = self._child_devices.values()
        self._deleted_devices = deleted_devices
        self._device_data = devices.data
        self._child_device_data = child_devices.data

        # Persist dropped corrupt/orphaned children so the store isn't left dirty until
        # an unrelated write
        if child_devices_dropped:
            self.async_schedule_save()

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
                entry.as_storage_fragment for entry in list(self._devices.values())
            ],
            "child_devices": [
                entry.as_storage_fragment
                for entry in list(self._child_devices.values())
            ],
            "deleted_devices": [
                entry.as_storage_fragment
                for entry in list(self._deleted_devices.values())
            ],
        }

    @callback
    def _resolve_orphan_domain(
        self, config_entry_id: str, domain: str | None
    ) -> str | None:
        """Return the domain to record on devices orphaned from a config entry."""
        if domain is not None:
            return domain
        if (
            entry := self.hass.config_entries.async_get_entry(config_entry_id)
        ) is not None:
            return entry.domain
        return None

    @callback
    def _async_orphan_deleted_device(
        self, deleted_device: DeletedDeviceEntry, domain: str | None, now_time: float
    ) -> None:
        """Mark a deleted device as orphaned, remembering its former domain."""
        if domain is not None:
            # Orphans are indexed by their recorded domain, so two orphans of the
            # same domain sharing an identifier or connection would collide. When a
            # device from the same integration is orphaned, drop any existing orphan
            # it overlaps so the newest one wins deterministically instead of shadowing
            # it.
            for existing in list(self._deleted_devices.values()):
                if (
                    existing.config_entry_id is None
                    and existing.domain == domain
                    and (
                        existing.connections & deleted_device.connections
                        or existing.identifiers & deleted_device.identifiers
                    )
                ):
                    del self._deleted_devices[existing.id]
        self._deleted_devices[deleted_device.id] = attr.evolve(
            deleted_device,
            config_entry_id=None,
            config_subentry_id=None,
            orphaned_timestamp=now_time,
            domain=domain,
        )
        self.async_schedule_save()

    @callback
    def async_config_entry_unloaded(self, config_entry_id: str) -> None:
        """Forget the live devices of a config entry that unloaded or failed setup."""
        self._live_device_ids.pop(config_entry_id, None)

    @callback
    def async_clear_config_entry(
        self, config_entry_id: str, domain: str | None = None
    ) -> None:
        """Clear config entry from registry entries."""
        self._live_device_ids.pop(config_entry_id, None)
        domain = self._resolve_orphan_domain(config_entry_id, domain)
        now_time = time.time()
        for device in self._devices.get_devices_for_config_entry_id(config_entry_id):
            self.async_remove_device(device.id)
        # Child devices share their parent's config entry, so the loop above removes
        # them through the parent cascade; guard against store corruption anyway.
        for child_device in self._child_devices.get_devices_for_config_entry_id(
            config_entry_id
        ):
            self.async_remove_device(child_device.id)
        # A split device records the composite's former primary config entry; when that
        # config entry is removed, clear the now-dangling reference so a restored
        # composite no longer points at a config entry that no longer exists.
        for device in list(self._devices.values()):
            if device.composite_primary_config_entry == config_entry_id:
                self._devices[device.id] = attr.evolve(
                    device, composite_primary_config_entry=None
                )
                self.async_schedule_save()
        # A device owned by another config entry may hold a transient pending move
        # targeting the entry being removed; clear it so a later completion deletes the
        # device instead of moving it onto the removed entry.
        for device in list(self._devices.values()):
            pending_move = device._pending_move  # noqa: SLF001
            if (
                pending_move is not None
                and pending_move.config_entry_id == config_entry_id
            ):
                self._devices[device.id] = attr.evolve(device, pending_move=None)
        for deleted_device in list(self._deleted_devices.values()):
            if deleted_device.config_entry_id != config_entry_id:
                continue
            self._async_orphan_deleted_device(deleted_device, domain, now_time)

    @callback
    def async_clear_config_subentry(
        self, config_entry_id: str, config_subentry_id: str, domain: str | None = None
    ) -> None:
        """Clear config subentry from registry entries."""
        domain = self._resolve_orphan_domain(config_entry_id, domain)
        now_time = time.time()
        for device in self._devices.get_devices_for_config_entry_id(config_entry_id):
            if device.config_subentry_id != config_subentry_id:
                continue
            self.async_remove_device(device.id)
        # Child devices share their parent's subentry, so the loop above removes them
        # through the parent cascade; guard against store corruption anyway.
        for child_device in self._child_devices.get_devices_for_config_entry_id(
            config_entry_id
        ):
            if child_device.config_subentry_id != config_subentry_id:
                continue
            self.async_remove_device(child_device.id)
        # A device may hold a transient pending move targeting the subentry being removed;
        # clear it so a later completion deletes the device instead of validating against
        # the removed subentry.
        for device in list(self._devices.values()):
            pending_move = device._pending_move  # noqa: SLF001
            if (
                pending_move is not None
                and pending_move.config_entry_id == config_entry_id
                and pending_move.config_subentry_id == config_subentry_id
            ):
                self._devices[device.id] = attr.evolve(device, pending_move=None)
        for deleted_device in list(self._deleted_devices.values()):
            if (
                deleted_device.config_entry_id != config_entry_id
                or deleted_device.config_subentry_id != config_subentry_id
            ):
                continue
            self._async_orphan_deleted_device(deleted_device, domain, now_time)

    @callback
    def async_purge_expired_orphaned_devices(self) -> None:
        """Purge expired orphaned devices from the registry.

        We need to purge these periodically to avoid the database
        growing without bound.
        """
        now_time = time.time()
        for deleted_device in list(self._deleted_devices.values()):
            if deleted_device.orphaned_timestamp is None:
                continue

            if (
                deleted_device.orphaned_timestamp + ORPHANED_DEVICE_KEEP_SECONDS
                < now_time
            ):
                del self._deleted_devices[deleted_device.id]

    @callback
    def async_clear_area_id(self, area_id: str) -> None:
        """Clear area id from registry entries."""
        for device in self._devices.get_devices_for_area_id(area_id):
            self._async_update_device(device.id, area_id=None)
        for child_device in self._child_devices.get_devices_for_area_id(area_id):
            self._async_update_child_device(child_device.id, area_id=None)
        for deleted_device in list(self._deleted_devices.values()):
            if deleted_device.area_id != area_id:
                continue
            self._deleted_devices[deleted_device.id] = attr.evolve(
                deleted_device, area_id=None
            )
            self.async_schedule_save()

    @callback
    def async_clear_label_id(self, label_id: str) -> None:
        """Clear label from registry entries."""
        for device in self._devices.get_devices_for_label(label_id):
            self._async_update_device(device.id, labels=device.labels - {label_id})
        for child_device in self._child_devices.get_devices_for_label(label_id):
            self._async_update_child_device(
                child_device.id, labels=child_device.labels - {label_id}
            )
        for deleted_device in list(self._deleted_devices.values()):
            if label_id not in deleted_device.labels:
                continue
            self._deleted_devices[deleted_device.id] = attr.evolve(
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


@callback
def async_get_device_id_by_identifier(
    hass: HomeAssistant, identifier: tuple[str, str], *, config_entry_id: str
) -> str:
    """Get the id of the device with the identifier, owned by the config entry.

    Searches main devices only; use async_get_child_device_by_identifier for a
    child device.
    Convenience wrapper for linking a device to its via device through
    via_device_id. Identifiers are unique within a config entry, so the lookup
    cannot be ambiguous.

    Raises ValueError if no such device exists.
    """
    device = async_get(hass).async_get_device_by_identifier(identifier, config_entry_id)
    if device is None:
        raise ValueError(
            f"There is no device with identifier {identifier} in config entry "
            f"{config_entry_id}"
        )
    return device.id


@callback
def async_get_device_and_config_entry_for_domain(
    hass: HomeAssistant, device_id: str, *, domain: str
) -> tuple[DeviceEntry | None, ConfigEntry | None]:
    """Get the device and the config entry of the domain owning it.

    Returns (None, None) for an unknown device id or if the device is a child
    device, and (device, None) when no config entry of the domain owns the
    device. A returned pair is consistent: for a pre-migration composite
    device id, the device is the domain's split device, not the composite; if
    several splits belong to config entries of the domain, which pair is
    returned is undefined. When no split matches the domain, the restored
    composite is returned as the device.
    """
    registry = async_get(hass)
    if (device := registry._devices.get(device_id)) is not None:  # noqa: SLF001
        config_entry = hass.config_entries.async_get_entry(device.config_entry_id)
        if config_entry is not None and config_entry.domain == domain:
            return device, config_entry
        return device, None
    for split in registry.async_get_devices_for_composite_device_id(device_id):
        config_entry = hass.config_entries.async_get_entry(split.config_entry_id)
        if config_entry is not None and config_entry.domain == domain:
            return split, config_entry
    return registry.async_get(device_id, include_child_devices=False), None


def async_setup(hass: HomeAssistant) -> None:
    """Set up device registry."""
    if DATA_REGISTRY in hass.data:
        raise RuntimeError("Device registry is already set up")
    hass.data[DATA_REGISTRY] = DeviceRegistry(hass)


async def async_load(hass: HomeAssistant, *, load_empty: bool = False) -> None:
    """Load device registry."""
    await async_get(hass).async_load(load_empty=load_empty)


@callback
def async_entries_for_area(
    registry: DeviceRegistry, area_id: str
) -> list[AnyDeviceEntry]:
    """Return entries whose effective area matches the area.

    Includes child devices with the area set explicitly, and child devices
    inheriting the area from their parent device.
    """
    devices = registry._devices.get_devices_for_area_id(area_id)  # noqa: SLF001
    entries: list[AnyDeviceEntry] = list(devices)
    entries.extend(
        registry._child_devices.get_devices_for_area_id(area_id)  # noqa: SLF001
    )
    for device in devices:
        entries.extend(
            child_device
            for child_device in registry._child_devices.get_children_for_device_id(  # noqa: SLF001
                device.id
            )
            if child_device.area_id is None
        )
    return entries


@callback
def async_get_effective_area_id(
    hass: HomeAssistant, device: AnyDeviceEntry
) -> str | None:
    """Return the effective area of a device or child device.

    A child device without an area of its own inherits its parent's area.
    """
    if device.area_id is not None:
        return device.area_id
    if isinstance(device, ChildDeviceEntry):
        registry = async_get(hass)
        if parent := registry.async_get(
            device.parent_device_id, include_child_devices=False
        ):
            return parent.area_id
    return None


@callback
def async_entries_for_label(
    registry: DeviceRegistry, label_id: str
) -> list[AnyDeviceEntry]:
    """Return entries that match a label.

    Includes child devices carrying the label; labels are never inherited from the
    parent, so a child appears here only when the label is set on the child itself.
    """
    entries: list[AnyDeviceEntry] = list(
        registry._devices.get_devices_for_label(label_id)  # noqa: SLF001
    )
    entries.extend(
        registry._child_devices.get_devices_for_label(label_id)  # noqa: SLF001
    )
    return entries


@callback
def async_entries_for_config_entry(
    registry: DeviceRegistry, config_entry_id: str
) -> list[DeviceEntry]:
    """Return entries that match a config entry."""
    return registry._devices.get_devices_for_config_entry_id(  # noqa: SLF001
        config_entry_id
    )


@callback
def async_entries_for_parent_device(
    registry: DeviceRegistry, parent_device_id: str
) -> list[ChildDeviceEntry]:
    """Return the child device entries of a parent device."""
    return registry._child_devices.get_children_for_device_id(  # noqa: SLF001
        parent_device_id
    )


@callback
def async_child_entries_for_config_entry(
    registry: DeviceRegistry, config_entry_id: str
) -> list[ChildDeviceEntry]:
    """Return child device entries that match a config entry."""
    return registry._child_devices.get_devices_for_config_entry_id(  # noqa: SLF001
        config_entry_id
    )


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

    devices: list[AnyDeviceEntry] = [
        *async_entries_for_config_entry(registry, config_entry.entry_id),
        *async_child_entries_for_config_entry(registry, config_entry.entry_id),
    ]

    if not config_entry.disabled_by:
        for device in devices:
            if device.disabled_by is not DeviceEntryDisabler.CONFIG_ENTRY:
                continue
            if isinstance(device, ChildDeviceEntry):
                registry._async_update_child_device(device.id, disabled_by=None)  # noqa: SLF001
            else:
                registry._async_update_device(device.id, disabled_by=None)  # noqa: SLF001
        return

    for device in devices:
        if device.disabled:
            # Device already disabled, do not overwrite
            continue
        if isinstance(device, ChildDeviceEntry):
            registry._async_update_child_device(  # noqa: SLF001
                device.id, disabled_by=DeviceEntryDisabler.CONFIG_ENTRY
            )
        else:
            registry._async_update_device(  # noqa: SLF001
                device.id, disabled_by=DeviceEntryDisabler.CONFIG_ENTRY
            )


@callback
def _migrate_device_disabled_by(
    device: dict[str, Any], config_entry_disabled: bool
) -> None:
    """Reconcile a stored device's disabled_by with its config entry's disabled state.

    Reimplements async_config_entry_disabled_by_changed on stored data so the 1.13
    migration can fix a split device that inherited the composite's disabled_by. Kept in
    lockstep with that function by test_migrate_device_disabled_by_matches_runtime; can be
    removed in HA Core 2027.8.
    """
    disabled_by = device["disabled_by"]
    if not config_entry_disabled:
        # Config entry enabled: drop a config-entry disable, keep a user/integration one
        if disabled_by == DeviceEntryDisabler.CONFIG_ENTRY:
            device["disabled_by"] = None
        return
    # Config entry disabled: disable the device unless it is already disabled
    if disabled_by is None:
        device["disabled_by"] = DeviceEntryDisabler.CONFIG_ENTRY


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
        for device in dev_reg._devices.values()  # noqa: SLF001
        if device.config_entry_id in config_entry_ids
    }

    # Find all devices that are referenced in the entity registry.
    device_ids_referenced_by_entities = set(ent_reg.entities.get_device_ids())

    orphan = (
        set(dev_reg._devices)  # noqa: SLF001
        - device_ids_referenced_by_entities
        - references_config_entries
    )

    for dev_id in orphan:
        dev_reg.async_remove_device(dev_id)

    # Find all referenced config entries that no longer exist
    # This shouldn't happen but have not been able to track down the bug :(
    for device in list(dev_reg._devices.values()):  # noqa: SLF001
        if device.config_entry_id not in config_entry_ids:
            dev_reg._async_update_device(  # noqa: SLF001
                device.id, remove_config_entry_id=device.config_entry_id
            )

    # A child device shares its parent's (valid) config entry, and the remove cascade
    # makes a child without its parent impossible; guard against store corruption anyway.
    for child_device in list(dev_reg.child_devices):
        if child_device.parent_device_id not in dev_reg._devices:  # noqa: SLF001
            _LOGGER.error(
                "Removing child device %s: its parent device %s is not in the "
                "device registry",
                child_device.id,
                child_device.parent_device_id,
            )
            dev_reg.async_remove_device(child_device.id)
        elif child_device.config_entry_id not in config_entry_ids:
            _LOGGER.error(
                "Removing child device %s: its config entry %s no longer exists",
                child_device.id,
                child_device.config_entry_id,
            )
            dev_reg.async_remove_device(child_device.id)

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
