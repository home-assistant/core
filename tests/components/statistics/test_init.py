"""Test Statistics component setup process."""

from __future__ import annotations

from homeassistant.components.statistics import DOMAIN as STATISTICS_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry


async def test_unload_entry(hass: HomeAssistant, loaded_entry: MockConfigEntry) -> None:
    """Test unload an entry."""

    assert loaded_entry.state is ConfigEntryState.LOADED
    assert await hass.config_entries.async_unload(loaded_entry.entry_id)
    await hass.async_block_till_done()
    assert loaded_entry.state is ConfigEntryState.NOT_LOADED


async def test_device_cleaning(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the cleaning of devices linked to the helper Statistics."""

    # Source entity device config entry
    source_config_entry = MockConfigEntry()
    source_config_entry.add_to_hass(hass)

    # Device entry of the source entity
    source_device1_entry = device_registry.async_get_or_create(
        config_entry_id=source_config_entry.entry_id,
        identifiers={("sensor", "identifier_test1")},
        connections={("mac", "30:31:32:33:34:01")},
    )

    # Source entity registry
    source_entity = entity_registry.async_get_or_create(
        "sensor",
        "test",
        "source",
        config_entry=source_config_entry,
        device_id=source_device1_entry.id,
    )
    await hass.async_block_till_done()
    assert entity_registry.async_get("sensor.test_source") is not None

    # Configure the configuration entry for Statistics
    statistics_config_entry = MockConfigEntry(
        data={},
        domain=STATISTICS_DOMAIN,
        options={
            "name": "Statistics",
            "entity_id": "sensor.test_source",
            "state_characteristic": "mean",
            "keep_last_sample": False,
            "percentile": 50.0,
            "precision": 2.0,
            "sampling_size": 20.0,
        },
        title="Statistics",
    )
    statistics_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(statistics_config_entry.entry_id)
    await hass.async_block_till_done()

    # Confirm the link between the source entity device and the statistics sensor
    statistics_entity = entity_registry.async_get("sensor.statistics")
    assert statistics_entity is not None
    assert statistics_entity.device_id == source_entity.device_id

    # Device entry incorrectly linked to Statistics config entry
    device_registry.async_get_or_create(
        config_entry_id=statistics_config_entry.entry_id,
        identifiers={("sensor", "identifier_test2")},
        connections={("mac", "30:31:32:33:34:02")},
    )
    device_registry.async_get_or_create(
        config_entry_id=statistics_config_entry.entry_id,
        identifiers={("sensor", "identifier_test3")},
        connections={("mac", "30:31:32:33:34:03")},
    )
    await hass.async_block_till_done()

    # Before reloading the config entry, two devices are expected to be linked
    devices_before_reload = device_registry.devices.get_devices_for_config_entry_id(
        statistics_config_entry.entry_id
    )
    assert len(devices_before_reload) == 3

    # Config entry reload
    await hass.config_entries.async_reload(statistics_config_entry.entry_id)
    await hass.async_block_till_done()

    # Confirm the link between the source entity device and the statistics sensor
    statistics_entity = entity_registry.async_get("sensor.statistics")
    assert statistics_entity is not None
    assert statistics_entity.device_id == source_entity.device_id

    # After reloading the config entry, only one linked device is expected
    devices_after_reload = device_registry.devices.get_devices_for_config_entry_id(
        statistics_config_entry.entry_id
    )
    assert len(devices_after_reload) == 1

    assert devices_after_reload[0].id == source_device1_entry.id
