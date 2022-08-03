"""The bluetooth integration matchers."""
from __future__ import annotations

from dataclasses import dataclass
import fnmatch
from typing import TYPE_CHECKING, Final, TypedDict

from lru import LRU  # pylint: disable=no-name-in-module

from homeassistant.loader import BluetoothMatcher, BluetoothMatcherOptional

if TYPE_CHECKING:
    from collections.abc import Mapping

    from bleak.backends.device import BLEDevice
    from bleak.backends.scanner import AdvertisementData


MAX_REMEMBER_ADDRESSES: Final = 2048


ADDRESS: Final = "address"
LOCAL_NAME: Final = "local_name"
SERVICE_UUID: Final = "service_uuid"
SERVICE_DATA_UUID: Final = "service_data_uuid"
MANUFACTURER_ID: Final = "manufacturer_id"
MANUFACTURER_DATA_START: Final = "manufacturer_data_start"


class BluetoothCallbackMatcherOptional(TypedDict, total=False):
    """Matcher for the bluetooth integration for callback optional fields."""

    address: str


class BluetoothCallbackMatcher(
    BluetoothMatcherOptional,
    BluetoothCallbackMatcherOptional,
):
    """Callback matcher for the bluetooth integration."""


@dataclass(frozen=False)
class IntegrationMatchHistory:
    """Track which fields have been seen."""

    manufacturer_data: bool
    service_data: bool
    service_uuids: bool


def seen_all_fields(
    previous_match: IntegrationMatchHistory, adv_data: AdvertisementData
) -> bool:
    """Return if we have seen all fields."""
    if not previous_match.manufacturer_data and adv_data.manufacturer_data:
        return False
    if not previous_match.service_data and adv_data.service_data:
        return False
    if not previous_match.service_uuids and adv_data.service_uuids:
        return False
    return True


class IntegrationMatcher:
    """Integration matcher for the bluetooth integration."""

    def __init__(self, integration_matchers: list[BluetoothMatcher]) -> None:
        """Initialize the matcher."""
        self._integration_matchers = integration_matchers
        # Some devices use a random address so we need to use
        # an LRU to avoid memory issues.
        self._matched: Mapping[str, IntegrationMatchHistory] = LRU(
            MAX_REMEMBER_ADDRESSES
        )

    def async_clear_history(self) -> None:
        """Clear the history."""
        self._matched = {}

    def match_domains(self, device: BLEDevice, adv_data: AdvertisementData) -> set[str]:
        """Return the domains that are matched."""
        matched_domains: set[str] = set()
        if (previous_match := self._matched.get(device.address)) and seen_all_fields(
            previous_match, adv_data
        ):
            # We have seen all fields so we can skip the rest of the matchers
            return matched_domains
        matched_domains = {
            matcher["domain"]
            for matcher in self._integration_matchers
            if ble_device_matches(matcher, device, adv_data)
        }
        if not matched_domains:
            return matched_domains
        if previous_match:
            previous_match.manufacturer_data |= bool(adv_data.manufacturer_data)
            previous_match.service_data |= bool(adv_data.service_data)
            previous_match.service_uuids |= bool(adv_data.service_uuids)
        else:
            self._matched[device.address] = IntegrationMatchHistory(  # type: ignore[index]
                manufacturer_data=bool(adv_data.manufacturer_data),
                service_data=bool(adv_data.service_data),
                service_uuids=bool(adv_data.service_uuids),
            )
        return matched_domains


def ble_device_matches(
    matcher: BluetoothCallbackMatcher | BluetoothMatcher,
    device: BLEDevice,
    adv_data: AdvertisementData,
) -> bool:
    """Check if a ble device and advertisement_data matches the matcher."""
    if (address := matcher.get(ADDRESS)) is not None and device.address != address:
        return False

    if (local_name := matcher.get(LOCAL_NAME)) is not None and not fnmatch.fnmatch(
        adv_data.local_name or device.name or device.address,
        local_name,
    ):
        return False

    if (
        service_uuid := matcher.get(SERVICE_UUID)
    ) is not None and service_uuid not in adv_data.service_uuids:
        return False

    if (
        service_data_uuid := matcher.get(SERVICE_DATA_UUID)
    ) is not None and service_data_uuid not in adv_data.service_data:
        return False

    if (
        manfacturer_id := matcher.get(MANUFACTURER_ID)
    ) is not None and manfacturer_id not in adv_data.manufacturer_data:
        return False

    if (manufacturer_data_start := matcher.get(MANUFACTURER_DATA_START)) is not None:
        manufacturer_data_start_bytes = bytearray(manufacturer_data_start)
        if not any(
            manufacturer_data.startswith(manufacturer_data_start_bytes)
            for manufacturer_data in adv_data.manufacturer_data.values()
        ):
            return False

    return True
