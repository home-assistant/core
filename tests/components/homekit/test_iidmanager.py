"""Tests for the HomeKit IID manager."""
from typing import Any
from uuid import UUID

from homeassistant.components.homekit.const import DOMAIN
from homeassistant.components.homekit.iidmanager import (
    AccessoryIIDStorage,
    get_iid_storage_filename_for_entry_id,
)
from homeassistant.core import HomeAssistant
from homeassistant.util.json import json_loads
from homeassistant.util.uuid import random_uuid_hex

from tests.common import MockConfigEntry, load_fixture


async def test_iid_generation_and_restore(
    hass: HomeAssistant, iid_storage, hass_storage: dict[str, Any]
) -> None:
    """Test generating iids and restoring them from storage."""
    entry = MockConfigEntry(domain=DOMAIN)

    iid_storage = AccessoryIIDStorage(hass, entry.entry_id)
    await iid_storage.async_initialize()

    random_service_uuid = UUID(random_uuid_hex())
    random_characteristic_uuid = UUID(random_uuid_hex())

    iid1 = iid_storage.get_or_allocate_iid(
        1, random_service_uuid, None, random_characteristic_uuid, None
    )
    iid2 = iid_storage.get_or_allocate_iid(
        1, random_service_uuid, None, random_characteristic_uuid, None
    )
    assert iid1 == iid2

    service_only_iid1 = iid_storage.get_or_allocate_iid(
        1, random_service_uuid, None, None, None
    )
    service_only_iid2 = iid_storage.get_or_allocate_iid(
        1, random_service_uuid, None, None, None
    )
    assert service_only_iid1 == service_only_iid2
    assert service_only_iid1 != iid1

    service_only_iid_with_unique_id1 = iid_storage.get_or_allocate_iid(
        1, random_service_uuid, "any", None, None
    )
    service_only_iid_with_unique_id2 = iid_storage.get_or_allocate_iid(
        1, random_service_uuid, "any", None, None
    )
    assert service_only_iid_with_unique_id1 == service_only_iid_with_unique_id2
    assert service_only_iid_with_unique_id1 != service_only_iid1

    unique_char_iid1 = iid_storage.get_or_allocate_iid(
        1, random_service_uuid, None, random_characteristic_uuid, "any"
    )
    unique_char_iid2 = iid_storage.get_or_allocate_iid(
        1, random_service_uuid, None, random_characteristic_uuid, "any"
    )
    assert unique_char_iid1 == unique_char_iid2
    assert unique_char_iid1 != iid1

    unique_service_unique_char_iid1 = iid_storage.get_or_allocate_iid(
        1, random_service_uuid, "any", random_characteristic_uuid, "any"
    )
    unique_service_unique_char_iid2 = iid_storage.get_or_allocate_iid(
        1, random_service_uuid, "any", random_characteristic_uuid, "any"
    )
    assert unique_service_unique_char_iid1 == unique_service_unique_char_iid2
    assert unique_service_unique_char_iid1 != iid1

    unique_service_unique_char_new_aid_iid1 = iid_storage.get_or_allocate_iid(
        2, random_service_uuid, "any", random_characteristic_uuid, "any"
    )
    unique_service_unique_char_new_aid_iid2 = iid_storage.get_or_allocate_iid(
        2, random_service_uuid, "any", random_characteristic_uuid, "any"
    )
    assert (
        unique_service_unique_char_new_aid_iid1
        == unique_service_unique_char_new_aid_iid2
    )
    await iid_storage.async_save()

    iid_storage2 = AccessoryIIDStorage(hass, entry.entry_id)
    await iid_storage2.async_initialize()
    iid3 = iid_storage2.get_or_allocate_iid(
        1, random_service_uuid, None, random_characteristic_uuid, None
    )
    assert iid3 == iid1


async def test_iid_storage_filename(
    hass: HomeAssistant, iid_storage, hass_storage: dict[str, Any]
) -> None:
    """Test iid storage uses the expected filename."""
    entry = MockConfigEntry(domain=DOMAIN)

    iid_storage = AccessoryIIDStorage(hass, entry.entry_id)
    await iid_storage.async_initialize()
    assert iid_storage.store.path.endswith(
        get_iid_storage_filename_for_entry_id(entry.entry_id)
    )


async def test_iid_migration_to_v2(
    hass: HomeAssistant, iid_storage, hass_storage: dict[str, Any]
) -> None:
    """Test iid storage migration."""
    v1_iids = json_loads(load_fixture("iids_v1", DOMAIN))
    v2_iids = json_loads(load_fixture("iids_v2", DOMAIN))
    hass_storage["homekit.v1.iids"] = v1_iids
    hass_storage["homekit.v2.iids"] = v2_iids

    iid_storage_v2 = AccessoryIIDStorage(hass, "v1")
    await iid_storage_v2.async_initialize()

    iid_storage_v1 = AccessoryIIDStorage(hass, "v2")
    await iid_storage_v1.async_initialize()

    assert iid_storage_v1.allocations == iid_storage_v2.allocations
    assert iid_storage_v1.allocated_iids == iid_storage_v2.allocated_iids

    assert len(iid_storage_v2.allocations) == 12

    for allocations in iid_storage_v2.allocations.values():
        assert allocations["3E___"] == 1


async def test_iid_migration_to_v2_with_underscore(
    hass: HomeAssistant, iid_storage, hass_storage: dict[str, Any]
) -> None:
    """Test iid storage migration with underscore."""
    v1_iids = json_loads(load_fixture("iids_v1_with_underscore", DOMAIN))
    v2_iids = json_loads(load_fixture("iids_v2_with_underscore", DOMAIN))
    hass_storage["homekit.v1_with_underscore.iids"] = v1_iids
    hass_storage["homekit.v2_with_underscore.iids"] = v2_iids

    iid_storage_v2 = AccessoryIIDStorage(hass, "v1_with_underscore")
    await iid_storage_v2.async_initialize()

    iid_storage_v1 = AccessoryIIDStorage(hass, "v2_with_underscore")
    await iid_storage_v1.async_initialize()

    assert iid_storage_v1.allocations == iid_storage_v2.allocations
    assert iid_storage_v1.allocated_iids == iid_storage_v2.allocated_iids

    assert len(iid_storage_v2.allocations) == 2

    for allocations in iid_storage_v2.allocations.values():
        assert allocations["3E___"] == 1


async def test_iid_generation_and_restore_v2(
    hass: HomeAssistant, iid_storage, hass_storage: dict[str, Any]
) -> None:
    """Test generating iids and restoring them from storage."""
    entry = MockConfigEntry(domain=DOMAIN)

    iid_storage = AccessoryIIDStorage(hass, entry.entry_id)
    await iid_storage.async_initialize()
    not_accessory_info_service_iid = iid_storage.get_or_allocate_iid(
        1, "000000AA-0000-1000-8000-0026BB765291", None, None, None
    )
    assert not_accessory_info_service_iid == 2
    assert iid_storage.allocated_iids == {"1": [1, 2]}
    not_accessory_info_service_iid_2 = iid_storage.get_or_allocate_iid(
        1, "000000BB-0000-1000-8000-0026BB765291", None, None, None
    )
    assert not_accessory_info_service_iid_2 == 3
    assert iid_storage.allocated_iids == {"1": [1, 2, 3]}
    not_accessory_info_service_iid_2 = iid_storage.get_or_allocate_iid(
        1, "000000BB-0000-1000-8000-0026BB765291", None, None, None
    )
    assert not_accessory_info_service_iid_2 == 3
    assert iid_storage.allocated_iids == {"1": [1, 2, 3]}
    accessory_info_service_iid = iid_storage.get_or_allocate_iid(
        1, "0000003E-0000-1000-8000-0026BB765291", None, None, None
    )
    assert accessory_info_service_iid == 1
    assert iid_storage.allocated_iids == {"1": [1, 2, 3]}
    accessory_info_service_iid = iid_storage.get_or_allocate_iid(
        1, "0000003E-0000-1000-8000-0026BB765291", None, None, None
    )
    assert accessory_info_service_iid == 1
    assert iid_storage.allocated_iids == {"1": [1, 2, 3]}
    accessory_info_service_iid = iid_storage.get_or_allocate_iid(
        2, "0000003E-0000-1000-8000-0026BB765291", None, None, None
    )
    assert accessory_info_service_iid == 1
    assert iid_storage.allocated_iids == {"1": [1, 2, 3], "2": [1]}
