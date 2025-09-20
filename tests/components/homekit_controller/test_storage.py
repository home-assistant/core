"""Basic checks for entity map storage."""

from collections.abc import Callable
from typing import Any

from aiohomekit.model import Accessory
from aiohomekit.model.characteristics import CharacteristicsTypes
from aiohomekit.model.services import ServicesTypes

from homeassistant.components.homekit_controller.const import ENTITY_MAP
from homeassistant.components.homekit_controller.storage import EntityMapStorage
from homeassistant.core import HomeAssistant

from .common import setup_platform, setup_test_component

from tests.common import flush_store


async def test_load_from_storage(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test that entity map can be correctly loaded from cache."""
    hkid = "00:00:00:00:00:00"

    hass_storage["homekit_controller-entity-map"] = {
        "version": 1,
        "data": {"pairings": {hkid: {"c#": 1, "accessories": []}}},
    }

    await setup_platform(hass)
    assert hkid in hass.data[ENTITY_MAP].storage_data


async def test_storage_is_removed(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test entity map storage removal is idempotent."""
    await setup_platform(hass)

    entity_map = hass.data[ENTITY_MAP]
    hkid = "00:00:00:00:00:01"

    entity_map.async_create_or_update_map(hkid, 1, [])
    assert hkid in entity_map.storage_data
    await flush_store(entity_map.store)
    assert hkid in hass_storage[ENTITY_MAP]["data"]["pairings"]

    entity_map.async_delete_map(hkid)
    assert hkid not in hass.data[ENTITY_MAP].storage_data
    await flush_store(entity_map.store)

    assert hass_storage[ENTITY_MAP]["data"]["pairings"] == {}


async def test_storage_is_removed_idempotent(hass: HomeAssistant) -> None:
    """Test entity map storage removal is idempotent."""
    await setup_platform(hass)

    entity_map = hass.data[ENTITY_MAP]
    hkid = "00:00:00:00:00:01"

    assert hkid not in entity_map.storage_data

    entity_map.async_delete_map(hkid)

    assert hkid not in entity_map.storage_data


def create_lightbulb_service(accessory: Accessory) -> None:
    """Define lightbulb characteristics."""
    service = accessory.add_service(ServicesTypes.LIGHTBULB)
    on_char = service.add_char(CharacteristicsTypes.ON)
    on_char.value = 0


async def test_storage_is_updated_on_add(
    hass: HomeAssistant, hass_storage: dict[str, Any], get_next_aid: Callable[[], int]
) -> None:
    """Test entity map storage is cleaned up on adding an accessory."""
    await setup_test_component(hass, get_next_aid(), create_lightbulb_service)

    entity_map: EntityMapStorage = hass.data[ENTITY_MAP]
    hkid = "00:00:00:00:00:00"

    # Is in memory store updated?
    assert hkid in entity_map.storage_data

    # Is saved out to store?
    await flush_store(entity_map.store)
    assert hkid in hass_storage[ENTITY_MAP]["data"]["pairings"]


async def test_storage_is_saved_on_stop(
    hass: HomeAssistant, hass_storage: dict[str, Any], get_next_aid: Callable[[], int]
) -> None:
    """Test entity map storage is saved when Home Assistant stops."""
    await setup_test_component(hass, get_next_aid(), create_lightbulb_service)

    entity_map: EntityMapStorage = hass.data[ENTITY_MAP]
    hkid = "00:00:00:00:00:00"

    # Verify the device is in memory
    assert hkid in entity_map.storage_data

    # Clear the storage to verify it gets saved on stop
    del hass_storage[ENTITY_MAP]

    # Make a change to trigger a save
    entity_map.async_create_or_update_map(hkid, 2, [])  # Update config_num

    # Simulate Home Assistant stopping (sets the state and fires the event)
    await hass.async_stop()
    await hass.async_block_till_done()

    # Verify the storage was saved
    assert ENTITY_MAP in hass_storage
    assert hkid in hass_storage[ENTITY_MAP]["data"]["pairings"]
    # Verify the updated data was saved
    assert hass_storage[ENTITY_MAP]["data"]["pairings"][hkid]["config_num"] == 2
