"""The bluetooth integration matchers."""
from __future__ import annotations

from dataclasses import dataclass
from fnmatch import translate
from functools import lru_cache
import re
from typing import TYPE_CHECKING, Final, TypedDict, Union, cast

from lru import LRU  # pylint: disable=no-name-in-module

from homeassistant.core import callback
from homeassistant.loader import BluetoothMatcher, BluetoothMatcherOptional

from .models import BluetoothCallback, BluetoothServiceInfoBleak

if TYPE_CHECKING:
    from collections.abc import MutableMapping

    from bleak.backends.scanner import AdvertisementData


MAX_REMEMBER_ADDRESSES: Final = 2048

CALLBACK: Final = "callback"
DOMAIN: Final = "domain"
ADDRESS: Final = "address"
CONNECTABLE: Final = "connectable"
LOCAL_NAME: Final = "local_name"
SERVICE_UUID: Final = "service_uuid"
SERVICE_DATA_UUID: Final = "service_data_uuid"
MANUFACTURER_ID: Final = "manufacturer_id"
MANUFACTURER_DATA_START: Final = "manufacturer_data_start"

LOCAL_NAME_MIN_MATCH_LENGTH = 3


class BluetoothCallbackMatcherOptional(TypedDict, total=False):
    """Matcher for the bluetooth integration for callback optional fields."""

    address: str


class BluetoothCallbackMatcher(
    BluetoothMatcherOptional,
    BluetoothCallbackMatcherOptional,
):
    """Callback matcher for the bluetooth integration."""


class _BluetoothCallbackMatcherWithCallback(TypedDict):
    """Callback for the bluetooth integration."""

    callback: BluetoothCallback


class BluetoothCallbackMatcherWithCallback(
    _BluetoothCallbackMatcherWithCallback,
    BluetoothCallbackMatcher,
):
    """Callback matcher for the bluetooth integration that stores the callback."""


@dataclass(frozen=False)
class IntegrationMatchHistory:
    """Track which fields have been seen."""

    manufacturer_data: bool
    service_data: set[str]
    service_uuids: set[str]


def seen_all_fields(
    previous_match: IntegrationMatchHistory, advertisement_data: AdvertisementData
) -> bool:
    """Return if we have seen all fields."""
    if not previous_match.manufacturer_data and advertisement_data.manufacturer_data:
        return False
    if advertisement_data.service_data and (
        not previous_match.service_data
        or not previous_match.service_data.issuperset(advertisement_data.service_data)
    ):
        return False
    if advertisement_data.service_uuids and (
        not previous_match.service_uuids
        or not previous_match.service_uuids.issuperset(advertisement_data.service_uuids)
    ):
        return False
    return True


class IntegrationMatcher:
    """Integration matcher for the bluetooth integration."""

    def __init__(self, integration_matchers: list[BluetoothMatcher]) -> None:
        """Initialize the matcher."""
        self._integration_matchers = integration_matchers
        # Some devices use a random address so we need to use
        # an LRU to avoid memory issues.
        self._matched: MutableMapping[str, IntegrationMatchHistory] = LRU(
            MAX_REMEMBER_ADDRESSES
        )
        self._matched_connectable: MutableMapping[str, IntegrationMatchHistory] = LRU(
            MAX_REMEMBER_ADDRESSES
        )
        self._index = BluetoothMatcherIndex()

    @callback
    def async_setup(self) -> None:
        """Set up the matcher."""
        for matcher in self._integration_matchers:
            self._index.add(matcher)
        self._index.build()

    def async_clear_address(self, address: str) -> None:
        """Clear the history matches for a set of domains."""
        self._matched.pop(address, None)
        self._matched_connectable.pop(address, None)

    def _get_matched_by_type(
        self, connectable: bool
    ) -> MutableMapping[str, IntegrationMatchHistory]:
        """Return the matches by type."""
        return self._matched_connectable if connectable else self._matched

    def match_domains(self, service_info: BluetoothServiceInfoBleak) -> set[str]:
        """Return the domains that are matched."""
        device = service_info.device
        advertisement_data = service_info.advertisement
        matched = self._get_matched_by_type(service_info.connectable)
        matched_domains: set[str] = set()
        if (previous_match := matched.get(device.address)) and seen_all_fields(
            previous_match, advertisement_data
        ):
            # We have seen all fields so we can skip the rest of the matchers
            return matched_domains
        matched_domains = {
            matcher[DOMAIN] for matcher in self._index.match_domains(service_info)
        }
        if not matched_domains:
            return matched_domains
        if previous_match:
            previous_match.manufacturer_data |= bool(
                advertisement_data.manufacturer_data
            )
            previous_match.service_data |= set(advertisement_data.service_data)
            previous_match.service_uuids |= set(advertisement_data.service_uuids)
        else:
            matched[device.address] = IntegrationMatchHistory(
                manufacturer_data=bool(advertisement_data.manufacturer_data),
                service_data=set(advertisement_data.service_data),
                service_uuids=set(advertisement_data.service_uuids),
            )
        return matched_domains


_MatcherTypes = Union[BluetoothMatcher, BluetoothCallbackMatcherWithCallback]


class BluetoothMatcherIndex:
    """Bluetooth matcher for the bluetooth integration."""

    def __init__(self) -> None:
        """Initialize the matcher index."""
        self.local_name: dict[str, list[_MatcherTypes]] = {}
        self.service_uuid: dict[str, list[_MatcherTypes]] = {}
        self.service_data_uuid: dict[str, list[_MatcherTypes]] = {}
        self.manufacturer_id: dict[int, list[_MatcherTypes]] = {}
        self.service_uuid_set: set[str] = set()
        self.service_data_uuid_set: set[str] = set()
        self.manufacturer_id_set: set[int] = set()

    def add(self, matcher: _MatcherTypes) -> None:
        """Add a matcher to the index.

        Matchers must end up only in one bucket.

        We put them in the bucket that they are most likely to match.
        """
        if LOCAL_NAME in matcher:
            self.local_name.setdefault(
                _local_name_to_index_key(matcher[LOCAL_NAME]), []
            ).append(matcher)
            return

        if SERVICE_UUID in matcher:
            self.service_uuid.setdefault(matcher[SERVICE_UUID], []).append(matcher)
            return

        if SERVICE_DATA_UUID in matcher:
            self.service_data_uuid.setdefault(matcher[SERVICE_DATA_UUID], []).append(
                matcher
            )
            return

        if MANUFACTURER_ID in matcher:
            self.manufacturer_id.setdefault(matcher[MANUFACTURER_ID], []).append(
                matcher
            )
            return

    def remove(self, matcher: _MatcherTypes) -> None:
        """Remove a matcher from the index.

        Matchers only end up in one bucket, so once we have
        removed one, we are done.
        """
        if LOCAL_NAME in matcher:
            self.local_name[_local_name_to_index_key(matcher[LOCAL_NAME])].remove(
                matcher
            )
            return

        if SERVICE_UUID in matcher:
            self.service_uuid[matcher[SERVICE_UUID]].remove(matcher)
            return

        if SERVICE_DATA_UUID in matcher:
            self.service_data_uuid[matcher[SERVICE_DATA_UUID]].remove(matcher)
            return

        if MANUFACTURER_ID in matcher:
            self.manufacturer_id[matcher[MANUFACTURER_ID]].remove(matcher)
            return

    def build(self) -> None:
        """Rebuild the index sets."""
        self.service_uuid_set = set(self.service_uuid)
        self.service_data_uuid_set = set(self.service_data_uuid)
        self.manufacturer_id_set = set(self.manufacturer_id)

    def _match(self, service_info: BluetoothServiceInfoBleak) -> list[_MatcherTypes]:
        """Check for a match."""
        matches = []
        if len(service_info.name) >= LOCAL_NAME_MIN_MATCH_LENGTH:
            for matcher in self.local_name.get(
                service_info.name[:LOCAL_NAME_MIN_MATCH_LENGTH], []
            ):
                if ble_device_matches(matcher, service_info):
                    matches.append(matcher)

        for service_data_uuid in self.service_data_uuid_set.intersection(
            service_info.service_data
        ):
            for matcher in self.service_data_uuid[service_data_uuid]:
                if ble_device_matches(matcher, service_info):
                    matches.append(matcher)

        for manufacturer_id in self.manufacturer_id_set.intersection(
            service_info.manufacturer_data
        ):
            for matcher in self.manufacturer_id[manufacturer_id]:
                if ble_device_matches(matcher, service_info):
                    matches.append(matcher)

        for service_uuid in self.service_uuid_set.intersection(
            service_info.service_uuids
        ):
            for matcher in self.service_uuid[service_uuid]:
                if ble_device_matches(matcher, service_info):
                    matches.append(matcher)

        return matches

    def match_domains(
        self, service_info: BluetoothServiceInfoBleak
    ) -> list[BluetoothMatcher]:
        """Check for a match."""
        return cast(list[BluetoothMatcher], self._match(service_info))


class BluetoothCallbackMatcherIndex(BluetoothMatcherIndex):
    """Bluetooth matcher for the bluetooth integration that supports matching on addresses."""

    def __init__(self) -> None:
        """Initialize the matcher index."""
        super().__init__()
        self.address: dict[str, list[BluetoothCallbackMatcherWithCallback]] = {}

    def add_with_address(self, matcher: BluetoothCallbackMatcherWithCallback) -> None:
        """Add a matcher to the index.

        Matchers must end up only in one bucket.

        We put them in the bucket that they are most likely to match.
        """
        if ADDRESS in matcher:
            self.address.setdefault(matcher[ADDRESS], []).append(matcher)
            return

        super().add(matcher)

    def remove_with_address(
        self, matcher: BluetoothCallbackMatcherWithCallback
    ) -> None:
        """Remove a matcher from the index.

        Matchers only end up in one bucket, so once we have
        removed one, we are done.
        """
        if ADDRESS in matcher:
            self.address[matcher[ADDRESS]].remove(matcher)
            return

        super().remove(matcher)

    def _match_addresses(
        self, service_info: BluetoothServiceInfoBleak
    ) -> list[BluetoothCallbackMatcherWithCallback]:
        """Check for a match."""
        return [
            matcher
            for matcher in self.address.get(service_info.address, [])
            # Shortcut the match if the matcher is only looking for a specific address
            # and connectable
            if set(matcher) == {ADDRESS, CONNECTABLE}
            or ble_device_matches(matcher, service_info)
        ]

    def match_callbacks(
        self, service_info: BluetoothServiceInfoBleak
    ) -> list[BluetoothCallbackMatcherWithCallback]:
        """Check for a match."""
        return cast(
            list[BluetoothCallbackMatcherWithCallback],
            [*super()._match(service_info), *self._match_addresses(service_info)],
        )


def _local_name_to_index_key(local_name: str) -> str:
    """Convert a local name to an index.

    We check the local name matchers here and raise a ValueError
    if they try to setup a matcher that will is overly broad
    as would match too many devices and cause a performance hit.
    """
    if len(local_name) < LOCAL_NAME_MIN_MATCH_LENGTH:
        raise ValueError(
            "Local name matchers must be at least "
            f"{LOCAL_NAME_MIN_MATCH_LENGTH} characters long ({local_name})"
        )
    match_part = local_name[:LOCAL_NAME_MIN_MATCH_LENGTH]
    if "*" in match_part or "[" in match_part:
        raise ValueError(
            "Local name matchers may not have patterns in the first "
            f"{LOCAL_NAME_MIN_MATCH_LENGTH} characters because they "
            f"would match too broadly ({local_name})"
        )
    return match_part


def ble_device_matches(
    matcher: BluetoothMatcher | BluetoothCallbackMatcherWithCallback,
    service_info: BluetoothServiceInfoBleak,
) -> bool:
    """Check if a ble device and advertisement_data matches the matcher."""
    device = service_info.device

    # Do don't check address here since all callers already
    # check the address and we don't want to double check
    # since it would result in an unreachable reject case.

    if matcher.get(CONNECTABLE, True) and not service_info.connectable:
        return False

    advertisement_data = service_info.advertisement
    if (
        service_uuid := matcher.get(SERVICE_UUID)
    ) is not None and service_uuid not in advertisement_data.service_uuids:
        return False

    if (
        service_data_uuid := matcher.get(SERVICE_DATA_UUID)
    ) is not None and service_data_uuid not in advertisement_data.service_data:
        return False

    if (
        manfacturer_id := matcher.get(MANUFACTURER_ID)
    ) is not None and manfacturer_id not in advertisement_data.manufacturer_data:
        return False

    if (manufacturer_data_start := matcher.get(MANUFACTURER_DATA_START)) is not None:
        manufacturer_data_start_bytes = bytearray(manufacturer_data_start)
        if not any(
            manufacturer_data.startswith(manufacturer_data_start_bytes)
            for manufacturer_data in advertisement_data.manufacturer_data.values()
        ):
            return False

    if (local_name := matcher.get(LOCAL_NAME)) is not None and (
        (device_name := advertisement_data.local_name or device.name) is None
        or not _memorized_fnmatch(
            device_name,
            local_name,
        )
    ):
        return False

    return True


@lru_cache(maxsize=4096, typed=True)
def _compile_fnmatch(pattern: str) -> re.Pattern:
    """Compile a fnmatch pattern."""
    return re.compile(translate(pattern))


@lru_cache(maxsize=1024, typed=True)
def _memorized_fnmatch(name: str, pattern: str) -> bool:
    """Memorized version of fnmatch that has a larger lru_cache.

    The default version of fnmatch only has a lru_cache of 256 entries.
    With many devices we quickly reach that limit and end up compiling
    the same pattern over and over again.

    Bluetooth has its own memorized fnmatch with its own lru_cache
    since the data is going to be relatively the same
    since the devices will not change frequently.
    """
    return bool(_compile_fnmatch(pattern).match(name))
