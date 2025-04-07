"""Test History stats component setup process."""

from __future__ import annotations

from homeassistant.components.history_stats.const import (
    CONF_END,
    CONF_START,
    DEFAULT_NAME,
    DOMAIN as HISTORY_STATS_DOMAIN,
)
from homeassistant.components.recorder import Recorder
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_ENTITY_ID, CONF_NAME, CONF_STATE, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry


async def test_unload_entry(
    recorder_mock: Recorder, hass: HomeAssistant, loaded_entry: MockConfigEntry
) -> None:
    """Test unload an entry."""

    assert loaded_entry.state is ConfigEntryState.LOADED
    assert await hass.config_entries.async_unload(loaded_entry.entry_id)
    await hass.async_block_till_done()
    assert loaded_entry.state is ConfigEntryState.NOT_LOADED


async def test_device_cleaning(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the cleaning of devices linked to the helper History stats."""

    # Source entity device config entry
    source_config_entry = MockConfigEntry()
    source_config_entry.add_to_hass(hass)

    # Device entry of the source entity
    source_device1_entry = device_registry.async_get_or_create(
        config_entry_id=source_config_entry.entry_id,
        identifiers={("binary_sensor", "identifier_test1")},
        connections={("mac", "30:31:32:33:34:01")},
    )

    # Source entity registry
    source_entity = entity_registry.async_get_or_create(
        "binary_sensor",
        "test",
        "source",
        config_entry=source_config_entry,
        device_id=source_device1_entry.id,
    )
    await hass.async_block_till_done()
    assert entity_registry.async_get("binary_sensor.test_source") is not None

    # Configure the configuration entry for History stats
    history_stats_config_entry = MockConfigEntry(
        data={},
        domain=HISTORY_STATS_DOMAIN,
        options={
            CONF_NAME: DEFAULT_NAME,
            CONF_ENTITY_ID: "binary_sensor.test_source",
            CONF_STATE: ["on"],
            CONF_TYPE: "count",
            CONF_START: "{{ as_timestamp(utcnow()) - 3600 }}",
            CONF_END: "{{ utcnow() }}",
        },
        title="History stats",
    )
    history_stats_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(history_stats_config_entry.entry_id)
    await hass.async_block_till_done()

    # Confirm the link between the source entity device and the History stats sensor
    history_stats_entity = entity_registry.async_get("sensor.history_stats")
    assert history_stats_entity is not None
    assert history_stats_entity.device_id == source_entity.device_id

    # Device entry incorrectly linked to History stats config entry
    device_registry.async_get_or_create(
        config_entry_id=history_stats_config_entry.entry_id,
        identifiers={("sensor", "identifier_test2")},
        connections={("mac", "30:31:32:33:34:02")},
    )
    device_registry.async_get_or_create(
        config_entry_id=history_stats_config_entry.entry_id,
        identifiers={("sensor", "identifier_test3")},
        connections={("mac", "30:31:32:33:34:03")},
    )
    await hass.async_block_till_done()

    # Before reloading the config entry, two devices are expected to be linked
    devices_before_reload = device_registry.devices.get_devices_for_config_entry_id(
        history_stats_config_entry.entry_id
    )
    assert len(devices_before_reload) == 3

    # Config entry reload
    await hass.config_entries.async_reload(history_stats_config_entry.entry_id)
    await hass.async_block_till_done()

    # Confirm the link between the source entity device and the History stats sensor
    history_stats_entity = entity_registry.async_get("sensor.history_stats")
    assert history_stats_entity is not None
    assert history_stats_entity.device_id == source_entity.device_id

    # After reloading the config entry, only one linked device is expected
    devices_after_reload = device_registry.devices.get_devices_for_config_entry_id(
        history_stats_config_entry.entry_id
    )
    assert len(devices_after_reload) == 1

    assert devices_after_reload[0].id == source_device1_entry.id
