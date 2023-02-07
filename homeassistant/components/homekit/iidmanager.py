"""Manage allocation of instance ID's.

HomeKit needs to allocate unique numbers to each accessory. These need to
be stable between reboots and upgrades.

This module generates and stores them in a HA storage.
"""
from __future__ import annotations

from uuid import UUID

from pyhap.util import uuid_to_hap_type

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.storage import Store

from .util import get_iid_storage_filename_for_entry_id

IID_MANAGER_STORAGE_VERSION = 2
IID_MANAGER_SAVE_DELAY = 2

ALLOCATIONS_KEY = "allocations"

IID_MIN = 1
IID_MAX = 18446744073709551615


ACCESSORY_INFORMATION_SERVICE = "3E"


class IIDStorage(Store):
    """Storage class for IIDManager."""

    async def _async_migrate_func(
        self,
        old_major_version: int,
        old_minor_version: int,
        old_data: dict,
    ):
        """Migrate to the new version."""
        if old_major_version == 1:
            # Convert v1 to v2 format which uses a unique iid set per accessory
            # instead of per pairing since we need the ACCESSORY_INFORMATION_SERVICE
            # to always have iid 1 for each bridged accessory as well as the bridge
            old_allocations: dict[str, int] = old_data.pop(ALLOCATIONS_KEY, {})
            new_allocation: dict[str, dict[str, int]] = {}
            old_data[ALLOCATIONS_KEY] = new_allocation
            for allocation_key, iid in old_allocations.items():
                aid_str, new_allocation_key = allocation_key.split("_", 1)
                service_type, _, char_type, *_ = new_allocation_key.split("_")
                accessory_allocation = new_allocation.setdefault(aid_str, {})
                if service_type == ACCESSORY_INFORMATION_SERVICE and not char_type:
                    accessory_allocation[new_allocation_key] = 1
                elif iid != 1:
                    accessory_allocation[new_allocation_key] = iid

            return old_data

        raise NotImplementedError


class AccessoryIIDStorage:
    """Provide stable allocation of IIDs for the lifetime of an accessory.

    Will generate new ID's, ensure they are unique and store them to make sure they
    persist over reboots.
    """

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        """Create a new iid store."""
        self.hass = hass
        self.allocations: dict[str, dict[str, int]] = {}
        self.allocated_iids: dict[str, list[int]] = {}
        self.entry_id = entry_id
        self.store: IIDStorage | None = None

    async def async_initialize(self) -> None:
        """Load the latest IID data."""
        iid_store = get_iid_storage_filename_for_entry_id(self.entry_id)
        self.store = IIDStorage(self.hass, IID_MANAGER_STORAGE_VERSION, iid_store)

        if not (raw_storage := await self.store.async_load()):
            # There is no data about iid allocations yet
            return

        assert isinstance(raw_storage, dict)
        self.allocations = raw_storage.get(ALLOCATIONS_KEY, {})
        for aid_str, allocations in self.allocations.items():
            self.allocated_iids[aid_str] = sorted(allocations.values())

    def get_or_allocate_iid(
        self,
        aid: int,
        service_uuid: UUID,
        service_unique_id: str | None,
        char_uuid: UUID | None,
        char_unique_id: str | None,
    ) -> int:
        """Generate a stable iid."""
        service_hap_type: str = uuid_to_hap_type(service_uuid)
        char_hap_type: str | None = uuid_to_hap_type(char_uuid) if char_uuid else None
        # Allocation key must be a string since we are saving it to JSON
        allocation_key = (
            f'{service_hap_type}_{service_unique_id or ""}_'
            f'{char_hap_type or ""}_{char_unique_id or ""}'
        )
        # AID must be a string since JSON keys cannot be int
        aid_str = str(aid)
        accessory_allocation = self.allocations.setdefault(aid_str, {})
        accessory_allocated_iids = self.allocated_iids.setdefault(aid_str, [1])
        if service_hap_type == ACCESSORY_INFORMATION_SERVICE and char_uuid is None:
            return 1
        if allocation_key in accessory_allocation:
            return accessory_allocation[allocation_key]
        if accessory_allocated_iids:
            allocated_iid = accessory_allocated_iids[-1] + 1
        else:
            allocated_iid = 2
        accessory_allocation[allocation_key] = allocated_iid
        accessory_allocated_iids.append(allocated_iid)
        self._async_schedule_save()
        return allocated_iid

    @callback
    def _async_schedule_save(self) -> None:
        """Schedule saving the iid allocations."""
        assert self.store is not None
        self.store.async_delay_save(self._data_to_save, IID_MANAGER_SAVE_DELAY)

    async def async_save(self) -> None:
        """Save the iid allocations."""
        assert self.store is not None
        return await self.store.async_save(self._data_to_save())

    @callback
    def _data_to_save(self) -> dict[str, dict[str, dict[str, int]]]:
        """Return data of entity map to store in a file."""
        return {ALLOCATIONS_KEY: self.allocations}
