"""Test the Trend integration."""

from unittest.mock import patch

import pytest

from homeassistant.components import trend
from homeassistant.components.trend.config_flow import ConfigFlowHandler
from homeassistant.components.trend.const import DOMAIN
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.event import async_track_entity_registry_updated_event

from .conftest import ComponentSetup

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
def trend_config_entry(
    hass: HomeAssistant,
    sensor_entity_entry: er.RegistryEntry,
) -> MockConfigEntry:
    """Fixture to create a trend config entry."""
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "name": "My trend",
            "entity_id": sensor_entity_entry.entity_id,
            "invert": False,
        },
        title="My trend",
        version=ConfigFlowHandler.VERSION,
        minor_version=ConfigFlowHandler.MINOR_VERSION,
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


async def test_setup_and_remove_config_entry(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    config_entry: MockConfigEntry,
) -> None:
    """Test setting up and removing a config entry."""
    trend_entity_id = "binary_sensor.my_trend"

    # Set up the config entry
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Check the entity is registered in the entity registry
    assert entity_registry.async_get(trend_entity_id) is not None

    # Remove the config entry
    assert await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()

    # Check the state and entity registry entry are removed
    assert hass.states.get(trend_entity_id) is None
    assert entity_registry.async_get(trend_entity_id) is None


async def test_reload_config_entry(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    setup_component: ComponentSetup,
) -> None:
    """Test config entry reload."""
    await setup_component({})

    assert config_entry.state is ConfigEntryState.LOADED

    assert hass.config_entries.async_update_entry(
        config_entry, data={**config_entry.data, "max_samples": 4.0}
    )

    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.data == {**config_entry.data, "max_samples": 4.0}


async def test_device_cleaning(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test for source entity device for Trend."""

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

    # Configure the configuration entry for Trend
    trend_config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "name": "Trend",
            "entity_id": "sensor.test_source",
            "invert": False,
        },
        title="Trend",
    )
    trend_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(trend_config_entry.entry_id)
    await hass.async_block_till_done()

    # Confirm the link between the source entity device and the trend sensor
    trend_entity = entity_registry.async_get("binary_sensor.trend")
    assert trend_entity is not None
    assert trend_entity.device_id == source_entity.device_id

    # Device entry incorrectly linked to Trend config entry
    device_registry.async_get_or_create(
        config_entry_id=trend_config_entry.entry_id,
        identifiers={("sensor", "identifier_test2")},
        connections={("mac", "30:31:32:33:34:02")},
    )
    device_registry.async_get_or_create(
        config_entry_id=trend_config_entry.entry_id,
        identifiers={("sensor", "identifier_test3")},
        connections={("mac", "30:31:32:33:34:03")},
    )
    await hass.async_block_till_done()

    # Before reloading the config entry, two devices are expected to be linked
    devices_before_reload = device_registry.devices.get_devices_for_config_entry_id(
        trend_config_entry.entry_id
    )
    assert len(devices_before_reload) == 2

    # Config entry reload
    await hass.config_entries.async_reload(trend_config_entry.entry_id)
    await hass.async_block_till_done()

    # Confirm the link between the source entity device and the trend sensor after reload
    trend_entity = entity_registry.async_get("binary_sensor.trend")
    assert trend_entity is not None
    assert trend_entity.device_id == source_entity.device_id

    # After reloading the config entry, only one linked device is expected
    devices_after_reload = device_registry.devices.get_devices_for_config_entry_id(
        trend_config_entry.entry_id
    )
    assert len(devices_after_reload) == 0


async def test_async_handle_source_entity_changes_source_entity_removed(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    trend_config_entry: MockConfigEntry,
    sensor_config_entry: ConfigEntry,
    sensor_device: dr.DeviceEntry,
    sensor_entity_entry: er.RegistryEntry,
) -> None:
    """Test the trend config entry is removed when the source entity is removed."""
    assert await hass.config_entries.async_setup(trend_config_entry.entry_id)
    await hass.async_block_till_done()

    trend_entity_entry = entity_registry.async_get("binary_sensor.my_trend")
    assert trend_entity_entry.device_id == sensor_entity_entry.device_id

    sensor_device = device_registry.async_get(sensor_device.id)
    assert trend_config_entry.entry_id not in sensor_device.config_entries

    events = track_entity_registry_actions(hass, trend_entity_entry.entity_id)

    # Remove the source sensor's config entry from the device, this removes the
    # source sensor
    with patch(
        "homeassistant.components.trend.async_unload_entry",
        wraps=trend.async_unload_entry,
    ) as mock_unload_entry:
        device_registry.async_update_device(
            sensor_device.id, remove_config_entry_id=sensor_config_entry.entry_id
        )
        await hass.async_block_till_done()
        await hass.async_block_till_done()
    mock_unload_entry.assert_called_once()

    # Check that the helper entity is removed
    assert not entity_registry.async_get("binary_sensor.my_trend")

    # Check that the device is removed
    assert not device_registry.async_get(sensor_device.id)

    # Check that the trend config entry is removed
    assert trend_config_entry.entry_id not in hass.config_entries.async_entry_ids()

    # Check we got the expected events
    assert events == ["remove"]


async def test_async_handle_source_entity_changes_source_entity_removed_shared_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    trend_config_entry: MockConfigEntry,
    sensor_config_entry: ConfigEntry,
    sensor_device: dr.DeviceEntry,
    sensor_entity_entry: er.RegistryEntry,
) -> None:
    """Test the trend config entry is removed when the source entity is removed."""
    # Add another config entry to the sensor device
    other_config_entry = MockConfigEntry()
    other_config_entry.add_to_hass(hass)
    device_registry.async_update_device(
        sensor_device.id, add_config_entry_id=other_config_entry.entry_id
    )

    assert await hass.config_entries.async_setup(trend_config_entry.entry_id)
    await hass.async_block_till_done()

    trend_entity_entry = entity_registry.async_get("binary_sensor.my_trend")
    assert trend_entity_entry.device_id == sensor_entity_entry.device_id

    sensor_device = device_registry.async_get(sensor_device.id)
    assert trend_config_entry.entry_id not in sensor_device.config_entries

    events = track_entity_registry_actions(hass, trend_entity_entry.entity_id)

    # Remove the source sensor's config entry from the device, this removes the
    # source sensor
    with patch(
        "homeassistant.components.trend.async_unload_entry",
        wraps=trend.async_unload_entry,
    ) as mock_unload_entry:
        device_registry.async_update_device(
            sensor_device.id, remove_config_entry_id=sensor_config_entry.entry_id
        )
        await hass.async_block_till_done()
        await hass.async_block_till_done()
    mock_unload_entry.assert_called_once()

    # Check that the helper entity is removed
    assert not entity_registry.async_get("binary_sensor.my_trend")

    # Check that the trend config entry is not in the device
    sensor_device = device_registry.async_get(sensor_device.id)
    assert trend_config_entry.entry_id not in sensor_device.config_entries

    # Check that the trend config entry is removed
    assert trend_config_entry.entry_id not in hass.config_entries.async_entry_ids()

    # Check we got the expected events
    assert events == ["remove"]


async def test_async_handle_source_entity_changes_source_entity_removed_from_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    trend_config_entry: MockConfigEntry,
    sensor_device: dr.DeviceEntry,
    sensor_entity_entry: er.RegistryEntry,
) -> None:
    """Test the source entity removed from the source device."""
    assert await hass.config_entries.async_setup(trend_config_entry.entry_id)
    await hass.async_block_till_done()

    trend_entity_entry = entity_registry.async_get("binary_sensor.my_trend")
    assert trend_entity_entry.device_id == sensor_entity_entry.device_id

    sensor_device = device_registry.async_get(sensor_device.id)
    assert trend_config_entry.entry_id not in sensor_device.config_entries

    events = track_entity_registry_actions(hass, trend_entity_entry.entity_id)

    # Remove the source sensor from the device
    with patch(
        "homeassistant.components.trend.async_unload_entry",
        wraps=trend.async_unload_entry,
    ) as mock_unload_entry:
        entity_registry.async_update_entity(
            sensor_entity_entry.entity_id, device_id=None
        )
        await hass.async_block_till_done()
    mock_unload_entry.assert_called_once()

    # Check that the entity is no longer linked to the source device
    trend_entity_entry = entity_registry.async_get("binary_sensor.my_trend")
    assert trend_entity_entry.device_id is None

    # Check that the trend config entry is not in the device
    sensor_device = device_registry.async_get(sensor_device.id)
    assert trend_config_entry.entry_id not in sensor_device.config_entries

    # Check that the trend config entry is not removed
    assert trend_config_entry.entry_id in hass.config_entries.async_entry_ids()

    # Check we got the expected events
    assert events == ["update"]


async def test_async_handle_source_entity_changes_source_entity_moved_other_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    trend_config_entry: MockConfigEntry,
    sensor_config_entry: ConfigEntry,
    sensor_device: dr.DeviceEntry,
    sensor_entity_entry: er.RegistryEntry,
) -> None:
    """Test the source entity is moved to another device."""
    sensor_device_2 = device_registry.async_get_or_create(
        config_entry_id=sensor_config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:FF")},
    )

    assert await hass.config_entries.async_setup(trend_config_entry.entry_id)
    await hass.async_block_till_done()

    trend_entity_entry = entity_registry.async_get("binary_sensor.my_trend")
    assert trend_entity_entry.device_id == sensor_entity_entry.device_id

    sensor_device = device_registry.async_get(sensor_device.id)
    assert trend_config_entry.entry_id not in sensor_device.config_entries
    sensor_device_2 = device_registry.async_get(sensor_device_2.id)
    assert trend_config_entry.entry_id not in sensor_device_2.config_entries

    events = track_entity_registry_actions(hass, trend_entity_entry.entity_id)

    # Move the source sensor to another device
    with patch(
        "homeassistant.components.trend.async_unload_entry",
        wraps=trend.async_unload_entry,
    ) as mock_unload_entry:
        entity_registry.async_update_entity(
            sensor_entity_entry.entity_id, device_id=sensor_device_2.id
        )
        await hass.async_block_till_done()
    mock_unload_entry.assert_called_once()

    # Check that the entity is linked to the other device
    trend_entity_entry = entity_registry.async_get("binary_sensor.my_trend")
    assert trend_entity_entry.device_id == sensor_device_2.id

    # Check that the trend config entry is not in any of the devices
    sensor_device = device_registry.async_get(sensor_device.id)
    assert trend_config_entry.entry_id not in sensor_device.config_entries
    sensor_device_2 = device_registry.async_get(sensor_device_2.id)
    assert trend_config_entry.entry_id not in sensor_device_2.config_entries

    # Check that the trend config entry is not removed
    assert trend_config_entry.entry_id in hass.config_entries.async_entry_ids()

    # Check we got the expected events
    assert events == ["update"]


async def test_async_handle_source_entity_new_entity_id(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    trend_config_entry: MockConfigEntry,
    sensor_device: dr.DeviceEntry,
    sensor_entity_entry: er.RegistryEntry,
) -> None:
    """Test the source entity's entity ID is changed."""
    assert await hass.config_entries.async_setup(trend_config_entry.entry_id)
    await hass.async_block_till_done()

    trend_entity_entry = entity_registry.async_get("binary_sensor.my_trend")
    assert trend_entity_entry.device_id == sensor_entity_entry.device_id

    sensor_device = device_registry.async_get(sensor_device.id)
    assert trend_config_entry.entry_id not in sensor_device.config_entries

    events = track_entity_registry_actions(hass, trend_entity_entry.entity_id)

    # Change the source entity's entity ID
    with patch(
        "homeassistant.components.trend.async_unload_entry",
        wraps=trend.async_unload_entry,
    ) as mock_unload_entry:
        entity_registry.async_update_entity(
            sensor_entity_entry.entity_id, new_entity_id="sensor.new_entity_id"
        )
        await hass.async_block_till_done()
    mock_unload_entry.assert_called_once()

    # Check that the trend config entry is updated with the new entity ID
    assert trend_config_entry.options["entity_id"] == "sensor.new_entity_id"

    # Check that the helper config is not in the device
    sensor_device = device_registry.async_get(sensor_device.id)
    assert trend_config_entry.entry_id not in sensor_device.config_entries

    # Check that the trend config entry is not removed
    assert trend_config_entry.entry_id in hass.config_entries.async_entry_ids()

    # Check we got the expected events
    assert events == []


async def test_migration_1_1(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    sensor_entity_entry: er.RegistryEntry,
    sensor_device: dr.DeviceEntry,
) -> None:
    """Test migration from v1.1 removes trend config entry from device."""

    trend_config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "name": "My trend",
            "entity_id": sensor_entity_entry.entity_id,
            "invert": False,
        },
        title="My trend",
        version=1,
        minor_version=1,
    )
    trend_config_entry.add_to_hass(hass)

    # Add the helper config entry to the device
    device_registry.async_update_device(
        sensor_device.id, add_config_entry_id=trend_config_entry.entry_id
    )

    # Check preconditions
    sensor_device = device_registry.async_get(sensor_device.id)
    assert trend_config_entry.entry_id in sensor_device.config_entries

    await hass.config_entries.async_setup(trend_config_entry.entry_id)
    await hass.async_block_till_done()

    assert trend_config_entry.state is ConfigEntryState.LOADED

    # Check that the helper config entry is removed from the device and the helper
    # entity is linked to the source device
    sensor_device = device_registry.async_get(sensor_device.id)
    assert trend_config_entry.entry_id not in sensor_device.config_entries
    trend_entity_entry = entity_registry.async_get("binary_sensor.my_trend")
    assert trend_entity_entry.device_id == sensor_entity_entry.device_id

    assert trend_config_entry.version == 1
    assert trend_config_entry.minor_version == 2


async def test_migration_from_future_version(
    hass: HomeAssistant,
) -> None:
    """Test migration from future version."""
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "name": "My trend",
            "entity_id": "sensor.test",
            "invert": False,
        },
        title="My trend",
        version=2,
        minor_version=1,
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.MIGRATION_ERROR
