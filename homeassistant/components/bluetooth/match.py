"""The bluetooth integration matchers."""
from __future__ import annotations

from dataclasses import dataclass
from fnmatch import translate
from functools import lru_cache
import re
from typing import TYPE_CHECKING, Final, Generic, TypedDict, TypeVar

from lru import LRU

from homeassistant.core import callback
from homeassistant.loader import BluetoothMatcher, BluetoothMatcherOptional

from .models import BluetoothCallback, BluetoothServiceInfoBleak

if TYPE_CHECKING:
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


@dataclass(slots=True, frozen=False)
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

    __slots__ = ("_integration_matchers", "_matched", "_matched_connectable", "_index")

    def __init__(self, integration_matchers: list[BluetoothMatcher]) -> None:
        """Initialize the matcher."""
        self._integration_matchers = integration_matchers
        # Some devices use a random address so we need to use
        # an LRU to avoid memory issues.
        self._matched: LRU[str, IntegrationMatchHistory] = LRU(MAX_REMEMBER_ADDRESSES)
        self._matched_connectable: LRU[str, IntegrationMatchHistory] = LRU(
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

    def match_domains(self, service_info: BluetoothServiceInfoBleak) -> set[str]:
        """Return the domains that are matched."""
        device = service_info.device
        advertisement_data = service_info.advertisement
        connectable = service_info.connectable
        matched = self._matched_connectable if connectable else self._matched
        matched_domains: set[str] = set()
        if (previous_match := matched.get(device.address)) and seen_all_fields(
            previous_match, advertisement_data
        ):
            # We have seen all fields so we can skip the rest of the matchers
            return matched_domains
        matched_domains = {
            matcher[DOMAIN] for matcher in self._index.match(service_info)
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


_T = TypeVar("_T", BluetoothMatcher, BluetoothCallbackMatcherWithCallback)


class BluetoothMatcherIndexBase(Generic[_T]):
    """Bluetooth matcher base for the bluetooth integration.

    The indexer puts each matcher in the bucket that it is most
    likely to match. This allows us to only check the service infos
    against each bucket to see if we should match against the data.

    This is optimized for cases when no service infos will be matched in
    any bucket and we can quickly reject the service info as not matching.
    """

    __slots__ = (
        "local_name",
        "service_uuid",
        "service_data_uuid",
        "manufacturer_id",
        "service_uuid_set",
        "service_data_uuid_set",
        "manufacturer_id_set",
    )

    def __init__(self) -> None:
        """Initialize the matcher index."""
        self.local_name: dict[str, list[_T]] = {}
        self.service_uuid: dict[str, list[_T]] = {}
        self.service_data_uuid: dict[str, list[_T]] = {}
        self.manufacturer_id: dict[int, list[_T]] = {}
        self.service_uuid_set: set[str] = set()
        self.service_data_uuid_set: set[str] = set()
        self.manufacturer_id_set: set[int] = set()

    def add(self, matcher: _T) -> bool:
        """Add a matcher to the index.

        Matchers must end up only in one bucket.

        We put them in the bucket that they are most likely to match.
        """
        # Local name is the cheapest to match since its just a dict lookup
        if LOCAL_NAME in matcher:
            self.local_name.setdefault(
                _local_name_to_index_key(matcher[LOCAL_NAME]), []
            ).append(matcher)
            return True

        # Manufacturer data is 2nd cheapest since its all ints
        if MANUFACTURER_ID in matcher:
            self.manufacturer_id.setdefault(matcher[MANUFACTURER_ID], []).append(
                matcher
            )
            return True

        if SERVICE_UUID in matcher:
            self.service_uuid.setdefault(matcher[SERVICE_UUID], []).append(matcher)
            return True

        if SERVICE_DATA_UUID in matcher:
            self.service_data_uuid.setdefault(matcher[SERVICE_DATA_UUID], []).append(
                matcher
            )
            return True

        return False

    def remove(self, matcher: _T) -> bool:
        """Remove a matcher from the index.

        Matchers only end up in one bucket, so once we have
        removed one, we are done.
        """
        if LOCAL_NAME in matcher:
            self.local_name[_local_name_to_index_key(matcher[LOCAL_NAME])].remove(
                matcher
            )
            return True

        if MANUFACTURER_ID in matcher:
            self.manufacturer_id[matcher[MANUFACTURER_ID]].remove(matcher)
            return True

        if SERVICE_UUID in matcher:
            self.service_uuid[matcher[SERVICE_UUID]].remove(matcher)
            return True

        if SERVICE_DATA_UUID in matcher:
            self.service_data_uuid[matcher[SERVICE_DATA_UUID]].remove(matcher)
            return True

        return False

    def build(self) -> None:
        """Rebuild the index sets."""
        self.service_uuid_set = set(self.service_uuid)
        self.service_data_uuid_set = set(self.service_data_uuid)
        self.manufacturer_id_set = set(self.manufacturer_id)

    def match(self, service_info: BluetoothServiceInfoBleak) -> list[_T]:
        """Check for a match."""
        matches = []
        if (name := service_info.name) and (
            local_name_matchers := self.local_name.get(
                name[:LOCAL_NAME_MIN_MATCH_LENGTH]
            )
        ):
            for matcher in local_name_matchers:
                if ble_device_matches(matcher, service_info):
                    matches.append(matcher)

        if self.service_data_uuid_set and service_info.service_data:
            for service_data_uuid in self.service_data_uuid_set.intersection(
                service_info.service_data
            ):
                for matcher in self.service_data_uuid[service_data_uuid]:
                    if ble_device_matches(matcher, service_info):
                        matches.append(matcher)

        if self.manufacturer_id_set and service_info.manufacturer_data:
            for manufacturer_id in self.manufacturer_id_set.intersection(
                service_info.manufacturer_data
            ):
                for matcher in self.manufacturer_id[manufacturer_id]:
                    if ble_device_matches(matcher, service_info):
                        matches.append(matcher)

        if self.service_uuid_set and service_info.service_uuids:
            for service_uuid in self.service_uuid_set.intersection(
                service_info.service_uuids
            ):
                for matcher in self.service_uuid[service_uuid]:
                    if ble_device_matches(matcher, service_info):
                        matches.append(matcher)

        return matches


class BluetoothMatcherIndex(BluetoothMatcherIndexBase[BluetoothMatcher]):
    """Bluetooth matcher for the bluetooth integration."""


class BluetoothCallbackMatcherIndex(
    BluetoothMatcherIndexBase[BluetoothCallbackMatcherWithCallback]
):
    """Bluetooth matcher for the bluetooth integration.

    Supports matching on addresses.
    """

    __slots__ = ("address", "connectable")

    def __init__(self) -> None:
        """Initialize the matcher index."""
        super().__init__()
        self.address: dict[str, list[BluetoothCallbackMatcherWithCallback]] = {}
        self.connectable: list[BluetoothCallbackMatcherWithCallback] = []

    def add_callback_matcher(
        self, matcher: BluetoothCallbackMatcherWithCallback
    ) -> None:
        """Add a matcher to the index.

        Matchers must end up only in one bucket.

        We put them in the bucket that they are most likely to match.
        """
        if ADDRESS in matcher:
            self.address.setdefault(matcher[ADDRESS], []).append(matcher)
            return

        if super().add(matcher):
            self.build()
            return

        if CONNECTABLE in matcher:
            self.connectable.append(matcher)
            return

    def remove_callback_matcher(
        self, matcher: BluetoothCallbackMatcherWithCallback
    ) -> None:
        """Remove a matcher from the index.

        Matchers only end up in one bucket, so once we have
        removed one, we are done.
        """
        if ADDRESS in matcher:
            self.address[matcher[ADDRESS]].remove(matcher)
            return

        if super().remove(matcher):
            self.build()
            return

        if CONNECTABLE in matcher:
            self.connectable.remove(matcher)
            return

    def match_callbacks(
        self, service_info: BluetoothServiceInfoBleak
    ) -> list[BluetoothCallbackMatcherWithCallback]:
        """Check for a match."""
        matches = self.match(service_info)
        for matcher in self.address.get(service_info.address, []):
            if ble_device_matches(matcher, service_info):
                matches.append(matcher)
        for matcher in self.connectable:
            if ble_device_matches(matcher, service_info):
                matches.append(matcher)
        return matches


def _local_name_to_index_key(local_name: str) -> str:
    """Convert a local name to an index.

    We check the local name matchers here and raise a ValueError
    if they try to setup a matcher that will is overly broad
    as would match too many devices and cause a performance hit.
    """
    match_part = local_name[:LOCAL_NAME_MIN_MATCH_LENGTH]
    if "*" in match_part or "[" in match_part:
        raise ValueError(
            "Local name matchers may not have patterns in the first "
            f"{LOCAL_NAME_MIN_MATCH_LENGTH} characters because they "
            f"would match too broadly ({local_name})"
        )
    return match_part


def ble_device_matches(
    matcher: BluetoothMatcherOptional,
    service_info: BluetoothServiceInfoBleak,
) -> bool:
    """Check if a ble device and advertisement_data matches the matcher."""
    # Don't check address here since all callers already
    # check the address and we don't want to double check
    # since it would result in an unreachable reject case.
    if matcher.get(CONNECTABLE, True) and not service_info.connectable:
        return False

    if (
        service_uuid := matcher.get(SERVICE_UUID)
    ) and service_uuid not in service_info.service_uuids:
        return False

    if (
        service_data_uuid := matcher.get(SERVICE_DATA_UUID)
    ) and service_data_uuid not in service_info.service_data:
        return False

    if manufacturer_id := matcher.get(MANUFACTURER_ID):
        if manufacturer_id not in service_info.manufacturer_data:
            return False

        if manufacturer_data_start := matcher.get(MANUFACTURER_DATA_START):
            if not service_info.manufacturer_data[manufacturer_id].startswith(
                bytes(manufacturer_data_start)
            ):
                return False

    if (local_name := matcher.get(LOCAL_NAME)) and not _memorized_fnmatch(
        service_info.name,
        local_name,
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
