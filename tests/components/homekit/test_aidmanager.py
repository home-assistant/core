"""Tests for the HomeKit AID manager."""
from asynctest import patch
import pytest

from homeassistant.components.homekit.aidmanager import (
    AccessoryAidStorage,
    get_system_unique_id,
)
from homeassistant.helpers import device_registry

from tests.common import MockConfigEntry, mock_device_registry, mock_registry


@pytest.fixture
def device_reg(hass):
    """Return an empty, loaded, registry."""
    return mock_device_registry(hass)


@pytest.fixture
def entity_reg(hass):
    """Return an empty, loaded, registry."""
    return mock_registry(hass)


async def test_aid_generation(hass, device_reg, entity_reg):
    """Test generating aids."""
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    light_ent = entity_reg.async_get_or_create(
        "light", "device", "unique_id", device_id=device_entry.id
    )
    light_ent2 = entity_reg.async_get_or_create(
        "light", "device", "other_unique_id", device_id=device_entry.id
    )
    remote_ent = entity_reg.async_get_or_create(
        "remote", "device", "unique_id", device_id=device_entry.id
    )
    hass.states.async_set(light_ent.entity_id, "on")
    hass.states.async_set(light_ent2.entity_id, "on")
    hass.states.async_set(remote_ent.entity_id, "on")
    hass.states.async_set("remote.has_no_unique_id", "on")

    with patch(
        "homeassistant.components.homekit.aidmanager.AccessoryAidStorage.async_schedule_save"
    ):
        aid_storage = AccessoryAidStorage(hass)
    await aid_storage.async_initialize()

    for _ in range(0, 2):
        assert (
            aid_storage.get_or_allocate_aid_for_entity_id(light_ent.entity_id)
            == 1692141785
        )
        assert (
            aid_storage.get_or_allocate_aid_for_entity_id(light_ent2.entity_id)
            == 2732133210
        )
        assert (
            aid_storage.get_or_allocate_aid_for_entity_id(remote_ent.entity_id)
            == 1867188557
        )
        assert (
            aid_storage.get_or_allocate_aid_for_entity_id("remote.has_no_unique_id")
            == 1872038229
        )

    aid_storage.delete_aid(get_system_unique_id(light_ent))
    aid_storage.delete_aid(get_system_unique_id(light_ent2))
    aid_storage.delete_aid(get_system_unique_id(remote_ent))
    aid_storage.delete_aid("non-existant-one")

    for _ in range(0, 2):
        assert (
            aid_storage.get_or_allocate_aid_for_entity_id(light_ent.entity_id)
            == 1692141785
        )
        assert (
            aid_storage.get_or_allocate_aid_for_entity_id(light_ent2.entity_id)
            == 2732133210
        )
        assert (
            aid_storage.get_or_allocate_aid_for_entity_id(remote_ent.entity_id)
            == 1867188557
        )
        assert (
            aid_storage.get_or_allocate_aid_for_entity_id("remote.has_no_unique_id")
            == 1872038229
        )


async def test_aid_adler32_collision(hass, device_reg, entity_reg):
    """Test generating aids."""
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )

    with patch(
        "homeassistant.components.homekit.aidmanager.AccessoryAidStorage.async_schedule_save"
    ):
        aid_storage = AccessoryAidStorage(hass)
    await aid_storage.async_initialize()

    seen_aids = set()

    for unique_id in range(0, 202):
        ent = entity_reg.async_get_or_create(
            "light", "device", unique_id, device_id=device_entry.id
        )
        hass.states.async_set(ent.entity_id, "on")
        aid = aid_storage.get_or_allocate_aid_for_entity_id(ent.entity_id)
        assert aid not in seen_aids
        seen_aids.add(aid)
