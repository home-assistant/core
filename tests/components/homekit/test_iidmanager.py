"""Tests for the HomeKit IID manager."""


from uuid import UUID

from homeassistant.components.homekit.const import DOMAIN
from homeassistant.components.homekit.iidmanager import (
    AccessoryIIDStorage,
    get_iid_storage_filename_for_entry_id,
)
from homeassistant.util.uuid import random_uuid_hex

from tests.common import MockConfigEntry


async def test_iid_generation_and_restore(hass, iid_storage, hass_storage):
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
    assert unique_service_unique_char_new_aid_iid1 != iid1
    assert unique_service_unique_char_new_aid_iid1 != unique_service_unique_char_iid1

    await iid_storage.async_save()

    iid_storage2 = AccessoryIIDStorage(hass, entry.entry_id)
    await iid_storage2.async_initialize()
    iid3 = iid_storage2.get_or_allocate_iid(
        1, random_service_uuid, None, random_characteristic_uuid, None
    )
    assert iid3 == iid1


async def test_iid_storage_filename(hass, iid_storage, hass_storage):
    """Test iid storage uses the expected filename."""
    entry = MockConfigEntry(domain=DOMAIN)

    iid_storage = AccessoryIIDStorage(hass, entry.entry_id)
    await iid_storage.async_initialize()
    assert iid_storage.store.path.endswith(
        get_iid_storage_filename_for_entry_id(entry.entry_id)
    )
