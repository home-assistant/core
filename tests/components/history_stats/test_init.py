"""Test History stats component setup process."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from homeassistant.components import history_stats
from homeassistant.components.history_stats.config_flow import (
    HistoryStatsConfigFlowHandler,
)
from homeassistant.components.history_stats.const import (
    CONF_END,
    CONF_START,
    DEFAULT_NAME,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_ENTITY_ID, CONF_NAME, CONF_STATE, CONF_TYPE
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.event import async_track_entity_registry_updated_event

from tests.common import MockConfigEntry


@pytest.fixture
def sensor_config_entry(hass: HomeAssistant) -> er.RegistryEntry:
    """Fixture to create a sensor config entry."""
    sensor_config_entry = MockConfigEntry()
    sensor_config_entry.add_to_hass(hass)
    return sensor_config_entry


@pytest.fixture
def sensor_device(
    device_registry: dr.DeviceRegistry, sensor_config_entry: ConfigEntry
) -> dr.DeviceEntry:
    """Fixture to create a sensor device."""
    return device_registry.async_get_or_create(
        config_entry_id=sensor_config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )


@pytest.fixture
def sensor_entity_entry(
    entity_registry: er.EntityRegistry,
    sensor_config_entry: ConfigEntry,
    sensor_device: dr.DeviceEntry,
) -> er.RegistryEntry:
    """Fixture to create a sensor entity entry."""
    return entity_registry.async_get_or_create(
        "sensor",
        "test",
        "unique",
        config_entry=sensor_config_entry,
        device_id=sensor_device.id,
        original_name="ABC",
    )


@pytest.fixture
def history_stats_config_entry(
    hass: HomeAssistant,
    sensor_entity_entry: er.RegistryEntry,
) -> MockConfigEntry:
    """Fixture to create a history_stats config entry."""
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            CONF_NAME: DEFAULT_NAME,
            CONF_ENTITY_ID: sensor_entity_entry.entity_id,
            CONF_STATE: ["on"],
            CONF_TYPE: "count",
            CONF_START: "{{ as_timestamp(utcnow()) - 3600 }}",
            CONF_END: "{{ utcnow() }}",
        },
        title="My history stats",
        version=HistoryStatsConfigFlowHandler.VERSION,
        minor_version=HistoryStatsConfigFlowHandler.MINOR_VERSION,
    )

    config_entry.add_to_hass(hass)

    return config_entry


def track_entity_registry_actions(hass: HomeAssistant, entity_id: str) -> list[str]:
    """Track entity registry actions for an entity."""
    events = []

    @callback
    def add_event(event: Event[er.EventEntityRegistryUpdatedData]) -> None:
        """Add entity registry updated event to the list."""
        events.append(event.data["action"])

    async_track_entity_registry_updated_event(hass, entity_id, add_event)

    return events


@pytest.mark.usefixtures("recorder_mock")
async def test_unload_entry(hass: HomeAssistant, loaded_entry: MockConfigEntry) -> None:
    """Test unload an entry."""

    assert loaded_entry.state is ConfigEntryState.LOADED
    assert await hass.config_entries.async_unload(loaded_entry.entry_id)
    await hass.async_block_till_done()
    assert loaded_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.usefixtures("recorder_mock")
async def test_device_cleaning(
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
        domain=DOMAIN,
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
    assert len(devices_before_reload) == 2

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
    assert len(devices_after_reload) == 0


@pytest.mark.usefixtures("recorder_mock")
async def test_async_handle_source_entity_changes_source_entity_removed(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    history_stats_config_entry: MockConfigEntry,
    sensor_config_entry: ConfigEntry,
    sensor_device: dr.DeviceEntry,
    sensor_entity_entry: er.RegistryEntry,
) -> None:
    """Test the history_stats config entry is removed when the source entity is removed."""
    assert await hass.config_entries.async_setup(history_stats_config_entry.entry_id)
    await hass.async_block_till_done()

    history_stats_entity_entry = entity_registry.async_get("sensor.my_history_stats")
    assert history_stats_entity_entry.device_id == sensor_entity_entry.device_id

    sensor_device = device_registry.async_get(sensor_device.id)
    assert history_stats_config_entry.entry_id not in sensor_device.config_entries

    events = track_entity_registry_actions(hass, history_stats_entity_entry.entity_id)

    # Remove the source sensor's config entry from the device, this removes the
    # source sensor
    with patch(
        "homeassistant.components.history_stats.async_unload_entry",
        wraps=history_stats.async_unload_entry,
    ) as mock_unload_entry:
        device_registry.async_update_device(
            sensor_device.id, remove_config_entry_id=sensor_config_entry.entry_id
        )
        await hass.async_block_till_done()
        await hass.async_block_till_done()
    mock_unload_entry.assert_called_once()

    # Check that the helper entity is removed
    assert not entity_registry.async_get("sensor.my_history_stats")

    # Check that the device is removed
    assert not device_registry.async_get(sensor_device.id)

    # Check that the history_stats config entry is removed
    assert (
        history_stats_config_entry.entry_id not in hass.config_entries.async_entry_ids()
    )

    # Check we got the expected events
    assert events == ["remove"]


@pytest.mark.usefixtures("recorder_mock")
async def test_async_handle_source_entity_changes_source_entity_removed_shared_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    history_stats_config_entry: MockConfigEntry,
    sensor_config_entry: ConfigEntry,
    sensor_device: dr.DeviceEntry,
    sensor_entity_entry: er.RegistryEntry,
) -> None:
    """Test the history_stats config entry is removed when the source entity is removed."""
    # Add another config entry to the sensor device
    other_config_entry = MockConfigEntry()
    other_config_entry.add_to_hass(hass)
    device_registry.async_update_device(
        sensor_device.id, add_config_entry_id=other_config_entry.entry_id
    )

    assert await hass.config_entries.async_setup(history_stats_config_entry.entry_id)
    await hass.async_block_till_done()

    history_stats_entity_entry = entity_registry.async_get("sensor.my_history_stats")
    assert history_stats_entity_entry.device_id == sensor_entity_entry.device_id

    sensor_device = device_registry.async_get(sensor_device.id)
    assert history_stats_config_entry.entry_id not in sensor_device.config_entries

    events = track_entity_registry_actions(hass, history_stats_entity_entry.entity_id)

    # Remove the source sensor's config entry from the device, this removes the
    # source sensor
    with patch(
        "homeassistant.components.history_stats.async_unload_entry",
        wraps=history_stats.async_unload_entry,
    ) as mock_unload_entry:
        device_registry.async_update_device(
            sensor_device.id, remove_config_entry_id=sensor_config_entry.entry_id
        )
        await hass.async_block_till_done()
        await hass.async_block_till_done()
    mock_unload_entry.assert_called_once()

    # Check that the helper entity is removed
    assert not entity_registry.async_get("sensor.my_history_stats")

    # Check that the history_stats config entry is not in the device
    sensor_device = device_registry.async_get(sensor_device.id)
    assert history_stats_config_entry.entry_id not in sensor_device.config_entries

    # Check that the history_stats config entry is removed
    assert (
        history_stats_config_entry.entry_id not in hass.config_entries.async_entry_ids()
    )

    # Check we got the expected events
    assert events == ["remove"]


@pytest.mark.usefixtures("recorder_mock")
async def test_async_handle_source_entity_changes_source_entity_removed_from_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    history_stats_config_entry: MockConfigEntry,
    sensor_device: dr.DeviceEntry,
    sensor_entity_entry: er.RegistryEntry,
) -> None:
    """Test the source entity removed from the source device."""
    assert await hass.config_entries.async_setup(history_stats_config_entry.entry_id)
    await hass.async_block_till_done()

    history_stats_entity_entry = entity_registry.async_get("sensor.my_history_stats")
    assert history_stats_entity_entry.device_id == sensor_entity_entry.device_id

    sensor_device = device_registry.async_get(sensor_device.id)
    assert history_stats_config_entry.entry_id not in sensor_device.config_entries

    events = track_entity_registry_actions(hass, history_stats_entity_entry.entity_id)

    # Remove the source sensor from the device
    with patch(
        "homeassistant.components.history_stats.async_unload_entry",
        wraps=history_stats.async_unload_entry,
    ) as mock_unload_entry:
        entity_registry.async_update_entity(
            sensor_entity_entry.entity_id, device_id=None
        )
        await hass.async_block_till_done()
    mock_unload_entry.assert_called_once()

    # Check that the entity is no longer linked to the source device
    history_stats_entity_entry = entity_registry.async_get("sensor.my_history_stats")
    assert history_stats_entity_entry.device_id is None

    # Check that the history_stats config entry is not in the device
    sensor_device = device_registry.async_get(sensor_device.id)
    assert history_stats_config_entry.entry_id not in sensor_device.config_entries

    # Check that the history_stats config entry is not removed
    assert history_stats_config_entry.entry_id in hass.config_entries.async_entry_ids()

    # Check we got the expected events
    assert events == ["update"]


@pytest.mark.usefixtures("recorder_mock")
async def test_async_handle_source_entity_changes_source_entity_moved_other_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    history_stats_config_entry: MockConfigEntry,
    sensor_config_entry: ConfigEntry,
    sensor_device: dr.DeviceEntry,
    sensor_entity_entry: er.RegistryEntry,
) -> None:
    """Test the source entity is moved to another device."""
    sensor_device_2 = device_registry.async_get_or_create(
        config_entry_id=sensor_config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:FF")},
    )

    assert await hass.config_entries.async_setup(history_stats_config_entry.entry_id)
    await hass.async_block_till_done()

    history_stats_entity_entry = entity_registry.async_get("sensor.my_history_stats")
    assert history_stats_entity_entry.device_id == sensor_entity_entry.device_id

    sensor_device = device_registry.async_get(sensor_device.id)
    assert history_stats_config_entry.entry_id not in sensor_device.config_entries
    sensor_device_2 = device_registry.async_get(sensor_device_2.id)
    assert history_stats_config_entry.entry_id not in sensor_device_2.config_entries

    events = track_entity_registry_actions(hass, history_stats_entity_entry.entity_id)

    # Move the source sensor to another device
    with patch(
        "homeassistant.components.history_stats.async_unload_entry",
        wraps=history_stats.async_unload_entry,
    ) as mock_unload_entry:
        entity_registry.async_update_entity(
            sensor_entity_entry.entity_id, device_id=sensor_device_2.id
        )
        await hass.async_block_till_done()
    mock_unload_entry.assert_called_once()

    # Check that the entity is linked to the other device
    history_stats_entity_entry = entity_registry.async_get("sensor.my_history_stats")
    assert history_stats_entity_entry.device_id == sensor_device_2.id

    # Check that the history_stats config entry is not in any of the devices
    sensor_device = device_registry.async_get(sensor_device.id)
    assert history_stats_config_entry.entry_id not in sensor_device.config_entries
    sensor_device_2 = device_registry.async_get(sensor_device_2.id)
    assert history_stats_config_entry.entry_id not in sensor_device_2.config_entries

    # Check that the history_stats config entry is not removed
    assert history_stats_config_entry.entry_id in hass.config_entries.async_entry_ids()

    # Check we got the expected events
    assert events == ["update"]


@pytest.mark.usefixtures("recorder_mock")
async def test_async_handle_source_entity_new_entity_id(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    history_stats_config_entry: MockConfigEntry,
    sensor_device: dr.DeviceEntry,
    sensor_entity_entry: er.RegistryEntry,
) -> None:
    """Test the source entity's entity ID is changed."""
    assert await hass.config_entries.async_setup(history_stats_config_entry.entry_id)
    await hass.async_block_till_done()

    history_stats_entity_entry = entity_registry.async_get("sensor.my_history_stats")
    assert history_stats_entity_entry.device_id == sensor_entity_entry.device_id

    sensor_device = device_registry.async_get(sensor_device.id)
    assert history_stats_config_entry.entry_id not in sensor_device.config_entries

    events = track_entity_registry_actions(hass, history_stats_entity_entry.entity_id)

    # Change the source entity's entity ID
    with patch(
        "homeassistant.components.history_stats.async_unload_entry",
        wraps=history_stats.async_unload_entry,
    ) as mock_unload_entry:
        entity_registry.async_update_entity(
            sensor_entity_entry.entity_id, new_entity_id="sensor.new_entity_id"
        )
        await hass.async_block_till_done()
    mock_unload_entry.assert_called_once()

    # Check that the history_stats config entry is updated with the new entity ID
    assert history_stats_config_entry.options[CONF_ENTITY_ID] == "sensor.new_entity_id"

    # Check that the helper config is not in the device
    sensor_device = device_registry.async_get(sensor_device.id)
    assert history_stats_config_entry.entry_id not in sensor_device.config_entries

    # Check that the history_stats config entry is not removed
    assert history_stats_config_entry.entry_id in hass.config_entries.async_entry_ids()

    # Check we got the expected events
    assert events == []


@pytest.mark.usefixtures("recorder_mock")
async def test_migration_1_1(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    sensor_entity_entry: er.RegistryEntry,
    sensor_device: dr.DeviceEntry,
) -> None:
    """Test migration from v1.1 removes history_stats config entry from device."""

    history_stats_config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            CONF_NAME: DEFAULT_NAME,
            CONF_ENTITY_ID: sensor_entity_entry.entity_id,
            CONF_STATE: ["on"],
            CONF_TYPE: "count",
            CONF_START: "{{ as_timestamp(utcnow()) - 3600 }}",
            CONF_END: "{{ utcnow() }}",
        },
        title="My history stats",
        version=1,
        minor_version=1,
    )
    history_stats_config_entry.add_to_hass(hass)

    # Add the helper config entry to the device
    device_registry.async_update_device(
        sensor_device.id, add_config_entry_id=history_stats_config_entry.entry_id
    )

    # Check preconditions
    sensor_device = device_registry.async_get(sensor_device.id)
    assert history_stats_config_entry.entry_id in sensor_device.config_entries

    await hass.config_entries.async_setup(history_stats_config_entry.entry_id)
    await hass.async_block_till_done()

    assert history_stats_config_entry.state is ConfigEntryState.LOADED

    # Check that the helper config entry is removed from the device and the helper
    # entity is linked to the source device
    sensor_device = device_registry.async_get(sensor_device.id)
    assert history_stats_config_entry.entry_id not in sensor_device.config_entries
    history_stats_entity_entry = entity_registry.async_get("sensor.my_history_stats")
    assert history_stats_entity_entry.device_id == sensor_entity_entry.device_id

    assert history_stats_config_entry.version == 1
    assert history_stats_config_entry.minor_version == 2


@pytest.mark.usefixtures("recorder_mock")
async def test_migration_from_future_version(
    hass: HomeAssistant,
) -> None:
    """Test migration from future version."""
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            CONF_NAME: DEFAULT_NAME,
            CONF_ENTITY_ID: "sensor.test",
            CONF_STATE: ["on"],
            CONF_TYPE: "count",
            CONF_START: "{{ as_timestamp(utcnow()) - 3600 }}",
            CONF_END: "{{ utcnow() }}",
        },
        title="My history stats",
        version=2,
        minor_version=1,
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.MIGRATION_ERROR
