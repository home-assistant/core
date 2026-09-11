"""The test for the Coolmaster integration."""

from unittest.mock import patch

from homeassistant.components.climate import HVACMode
from homeassistant.components.coolmaster.const import DOMAIN
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from .conftest import CoolMasterNetMock

from tests.common import MockConfigEntry
from tests.typing import WebSocketGenerator


def _mock_config_entry(host: str) -> MockConfigEntry:
    """Create a mock Coolmaster config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": host,
            "port": 1234,
            "supported_modes": [HVACMode.OFF, HVACMode.COOL, HVACMode.HEAT],
        },
    )


async def test_load_entry(
    hass: HomeAssistant, load_int: ConfigEntry, unit_count: int
) -> None:
    """Test Coolmaster initial load."""
    # 4 units times 4 entities (climate, binary_sensor, sensor, button).
    assert hass.states.async_entity_ids_count() == unit_count * 4
    assert load_int.state is ConfigEntryState.LOADED


async def test_unload_entry(
    hass: HomeAssistant,
    load_int: ConfigEntry,
) -> None:
    """Test Coolmaster unloading an entry."""
    await hass.config_entries.async_unload(load_int.entry_id)
    await hass.async_block_till_done()
    assert load_int.state is ConfigEntryState.NOT_LOADED


async def test_registry_cleanup(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    load_int: ConfigEntry,
    hass_ws_client: WebSocketGenerator,
    unit_count: int,
) -> None:
    """Test being able to remove a disconnected device."""
    entry_id = load_int.entry_id
    live_id = f"{entry_id}-L1.100"
    dead_id = "L2.200"

    assert (
        len(dr.async_entries_for_config_entry(device_registry, entry_id)) == unit_count
    )
    device_registry.async_get_or_create(
        config_entry_id=entry_id,
        identifiers={(DOMAIN, dead_id)},
        manufacturer="CoolAutomation",
        model="CoolMasterNet",
        name=dead_id,
        sw_version="1.0",
    )

    assert (
        len(dr.async_entries_for_config_entry(device_registry, entry_id))
        == unit_count + 1
    )

    assert await async_setup_component(hass, "config", {})
    client = await hass_ws_client(hass)
    # Try to remove "L1.100" - fails since it is live
    device = device_registry.async_get_device_by_identifier((DOMAIN, live_id), entry_id)
    assert device is not None
    response = await client.remove_device(device.id)
    assert not response["success"]
    assert (
        len(dr.async_entries_for_config_entry(device_registry, entry_id))
        == unit_count + 1
    )
    assert (
        device_registry.async_get_device_by_identifier((DOMAIN, live_id), entry_id)
        is not None
    )

    # Try to remove "L2.200" - succeeds since it is dead
    device = device_registry.async_get_device_by_identifier((DOMAIN, dead_id), entry_id)
    assert device is not None
    response = await client.remove_device(device.id)
    assert response["success"]
    assert (
        len(dr.async_entries_for_config_entry(device_registry, entry_id)) == unit_count
    )
    assert (
        device_registry.async_get_device_by_identifier((DOMAIN, dead_id), entry_id)
        is None
    )


async def test_migrate_unique_ids(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test migration of raw unit ID unique IDs to config-entry-scoped ones."""
    config_entry = _mock_config_entry("1.2.3.4")
    config_entry.add_to_hass(hass)

    # Simulate a pre-migration install: device and entities registered
    # with raw unit IDs.
    device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "L1.100")},
        manufacturer="CoolAutomation",
        model="CoolMasterNet",
        name="L1.100",
    )
    climate_entity = entity_registry.async_get_or_create(
        "climate",
        DOMAIN,
        "L1.100",
        config_entry=config_entry,
        device_id=device.id,
        suggested_object_id="l1_100",
    )
    sensor_entity = entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        "L1.100-error_code",
        config_entry=config_entry,
        device_id=device.id,
    )

    with patch(
        "homeassistant.components.coolmaster.CoolMasterNet",
        new=CoolMasterNetMock,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    prefix = f"{config_entry.entry_id}-"
    migrated_climate = entity_registry.async_get(climate_entity.entity_id)
    assert migrated_climate is not None
    assert migrated_climate.unique_id == f"{prefix}L1.100"
    migrated_sensor = entity_registry.async_get(sensor_entity.entity_id)
    assert migrated_sensor is not None
    assert migrated_sensor.unique_id == f"{prefix}L1.100-error_code"

    migrated_device = device_registry.async_get(device.id)
    assert migrated_device is not None
    assert migrated_device.identifiers == {(DOMAIN, f"{prefix}L1.100")}


async def test_multiple_bridges_with_same_unit_ids(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    unit_count: int,
) -> None:
    """Test two bridges reporting the same unit IDs don't collide.

    Unique IDs used to be the raw unit ID, so the second bridge's
    entities were silently dropped.
    """
    entry1 = _mock_config_entry("1.2.3.4")
    entry1.add_to_hass(hass)
    entry2 = _mock_config_entry("4.3.2.1")
    entry2.add_to_hass(hass)

    # Simulate the pre-migration collision: entry1's entity registered with
    # a raw unit ID unique ID, and the device claimed by both entries due
    # to the identifier collision.
    device = device_registry.async_get_or_create(
        config_entry_id=entry1.entry_id,
        identifiers={(DOMAIN, "L1.100")},
        manufacturer="CoolAutomation",
        model="CoolMasterNet",
        name="L1.100",
    )
    device_registry.async_get_or_create(
        config_entry_id=entry2.entry_id,
        identifiers={(DOMAIN, "L1.100")},
    )
    entity_registry.async_get_or_create(
        "climate",
        DOMAIN,
        "L1.100",
        config_entry=entry1,
        device_id=device.id,
    )

    with patch(
        "homeassistant.components.coolmaster.CoolMasterNet",
        new=CoolMasterNetMock,
    ):
        # Setting up the first entry sets up the whole domain, including
        # the second entry.
        await hass.config_entries.async_setup(entry1.entry_id)
        await hass.async_block_till_done()

    assert entry1.state is ConfigEntryState.LOADED
    assert entry2.state is ConfigEntryState.LOADED

    # Every unit appears once per bridge.
    assert hass.states.async_entity_ids_count() == unit_count * 4 * 2
    for entry in (entry1, entry2):
        assert (
            len(er.async_entries_for_config_entry(entity_registry, entry.entry_id))
            == unit_count * 4
        )
        assert (
            len(dr.async_entries_for_config_entry(device_registry, entry.entry_id))
            == unit_count
        )

    # The formerly shared device now belongs to entry1 alone, with a
    # config-entry-scoped identifier.
    shared_device = device_registry.async_get(device.id)
    assert shared_device is not None
    assert shared_device.identifiers == {(DOMAIN, f"{entry1.entry_id}-L1.100")}
    entry2_devices = dr.async_entries_for_config_entry(device_registry, entry2.entry_id)
    assert device.id not in {device_entry.id for device_entry in entry2_devices}
