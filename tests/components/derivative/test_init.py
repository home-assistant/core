"""Test the Derivative integration."""

from unittest.mock import patch

import pytest

from homeassistant.components import derivative
from homeassistant.components.derivative.config_flow import ConfigFlowHandler
from homeassistant.components.derivative.const import DOMAIN
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
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
def derivative_config_entry(
    hass: HomeAssistant,
    sensor_entity_entry: er.RegistryEntry,
) -> MockConfigEntry:
    """Fixture to create a derivative config entry."""
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "name": "My derivative",
            "round": 1.0,
            "source": sensor_entity_entry.entity_id,
            "time_window": {"seconds": 0.0},
            "unit_prefix": "k",
            "unit_time": "min",
        },
        title="My derivative",
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
) -> None:
    """Test setting up and removing a config entry."""
    input_sensor_entity_id = "sensor.input"
    derivative_entity_id = "sensor.my_derivative"

    hass.states.async_set(input_sensor_entity_id, "10.0", {})
    await hass.async_block_till_done()

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "name": "My derivative",
            "round": 1.0,
            "source": "sensor.input",
            "time_window": {"seconds": 0.0},
            "unit_prefix": "k",
            "unit_time": "min",
        },
        title="My derivative",
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Check the entity is registered in the entity registry
    assert entity_registry.async_get(derivative_entity_id) is not None

    # Check the platform is setup correctly
    state = hass.states.get(derivative_entity_id)
    assert state.state == "0.0"
    assert "unit_of_measurement" not in state.attributes
    assert state.attributes["source"] == "sensor.input"

    hass.states.async_set(input_sensor_entity_id, 10, {"unit_of_measurement": "dog"})
    hass.states.async_set(input_sensor_entity_id, 11, {"unit_of_measurement": "dog"})
    await hass.async_block_till_done()
    state = hass.states.get(derivative_entity_id)
    assert state.state != "0"
    assert state.attributes["unit_of_measurement"] == "kdog/min"

    # Remove the config entry
    assert await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()

    # Check the state and entity registry entry are removed
    assert hass.states.get(derivative_entity_id) is None
    assert entity_registry.async_get(derivative_entity_id) is None


async def test_device_cleaning(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test for source entity device for Derivative."""

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

    # Configure the configuration entry for Derivative
    derivative_config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "name": "Derivative",
            "round": 1.0,
            "source": "sensor.test_source",
            "time_window": {"seconds": 0.0},
            "unit_prefix": "k",
            "unit_time": "min",
        },
        title="Derivative",
    )
    derivative_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(derivative_config_entry.entry_id)
    await hass.async_block_till_done()

    # Confirm the link between the source entity device and the derivative sensor
    derivative_entity = entity_registry.async_get("sensor.derivative")
    assert derivative_entity is not None
    assert derivative_entity.device_id == source_entity.device_id

    # Device entry incorrectly linked to Derivative config entry
    device_registry.async_get_or_create(
        config_entry_id=derivative_config_entry.entry_id,
        identifiers={("sensor", "identifier_test2")},
        connections={("mac", "30:31:32:33:34:02")},
    )
    device_registry.async_get_or_create(
        config_entry_id=derivative_config_entry.entry_id,
        identifiers={("sensor", "identifier_test3")},
        connections={("mac", "30:31:32:33:34:03")},
    )
    await hass.async_block_till_done()

    # Before reloading the config entry, two devices are expected to be linked
    devices_before_reload = device_registry.devices.get_devices_for_config_entry_id(
        derivative_config_entry.entry_id
    )
    assert len(devices_before_reload) == 2

    # Config entry reload
    await hass.config_entries.async_reload(derivative_config_entry.entry_id)
    await hass.async_block_till_done()

    # Confirm the link between the source entity device and the derivative sensor after reload
    derivative_entity = entity_registry.async_get("sensor.derivative")
    assert derivative_entity is not None
    assert derivative_entity.device_id == source_entity.device_id

    # After reloading the config entry, only one linked device is expected
    devices_after_reload = device_registry.devices.get_devices_for_config_entry_id(
        derivative_config_entry.entry_id
    )
    assert len(devices_after_reload) == 0


async def test_async_handle_source_entity_changes_source_entity_removed(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    derivative_config_entry: MockConfigEntry,
    sensor_config_entry: ConfigEntry,
    sensor_device: dr.DeviceEntry,
    sensor_entity_entry: er.RegistryEntry,
) -> None:
    """Test the derivative config entry is removed when the source entity is removed."""
    assert await hass.config_entries.async_setup(derivative_config_entry.entry_id)
    await hass.async_block_till_done()

    derivative_entity_entry = entity_registry.async_get("sensor.my_derivative")
    assert derivative_entity_entry.device_id == sensor_entity_entry.device_id

    sensor_device = device_registry.async_get(sensor_device.id)
    assert derivative_config_entry.entry_id not in sensor_device.config_entries

    events = track_entity_registry_actions(hass, derivative_entity_entry.entity_id)

    # Remove the source sensor's config entry from the device, this removes the
    # source sensor
    with patch(
        "homeassistant.components.derivative.async_unload_entry",
        wraps=derivative.async_unload_entry,
    ) as mock_unload_entry:
        device_registry.async_update_device(
            sensor_device.id, remove_config_entry_id=sensor_config_entry.entry_id
        )
        await hass.async_block_till_done()
        await hass.async_block_till_done()
    mock_unload_entry.assert_not_called()

    # Check that the entity is no longer linked to the source device
    derivative_entity_entry = entity_registry.async_get("sensor.my_derivative")
    assert derivative_entity_entry.device_id is None

    # Check that the device is removed
    assert not device_registry.async_get(sensor_device.id)

    # Check that the derivative config entry is not removed
    assert derivative_config_entry.entry_id in hass.config_entries.async_entry_ids()

    # Check we got the expected events
    assert events == ["update"]


async def test_async_handle_source_entity_changes_source_entity_removed_shared_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    derivative_config_entry: MockConfigEntry,
    sensor_config_entry: ConfigEntry,
    sensor_device: dr.DeviceEntry,
    sensor_entity_entry: er.RegistryEntry,
) -> None:
    """Test the derivative config entry is removed when the source entity is removed."""
    # Add another config entry to the sensor device
    other_config_entry = MockConfigEntry()
    other_config_entry.add_to_hass(hass)
    device_registry.async_update_device(
        sensor_device.id, add_config_entry_id=other_config_entry.entry_id
    )

    assert await hass.config_entries.async_setup(derivative_config_entry.entry_id)
    await hass.async_block_till_done()

    derivative_entity_entry = entity_registry.async_get("sensor.my_derivative")
    assert derivative_entity_entry.device_id == sensor_entity_entry.device_id

    sensor_device = device_registry.async_get(sensor_device.id)
    assert derivative_config_entry.entry_id not in sensor_device.config_entries

    events = track_entity_registry_actions(hass, derivative_entity_entry.entity_id)

    # Remove the source sensor's config entry from the device, this removes the
    # source sensor
    with patch(
        "homeassistant.components.derivative.async_unload_entry",
        wraps=derivative.async_unload_entry,
    ) as mock_unload_entry:
        device_registry.async_update_device(
            sensor_device.id, remove_config_entry_id=sensor_config_entry.entry_id
        )
        await hass.async_block_till_done()
        await hass.async_block_till_done()
    mock_unload_entry.assert_not_called()

    # Check that the entity is no longer linked to the source device
    derivative_entity_entry = entity_registry.async_get("sensor.my_derivative")
    assert derivative_entity_entry.device_id is None

    # Check that the derivative config entry is not in the device
    sensor_device = device_registry.async_get(sensor_device.id)
    assert derivative_config_entry.entry_id not in sensor_device.config_entries

    # Check that the derivative config entry is not removed
    assert derivative_config_entry.entry_id in hass.config_entries.async_entry_ids()

    # Check we got the expected events
    assert events == ["update"]


async def test_async_handle_source_entity_changes_source_entity_removed_from_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    derivative_config_entry: MockConfigEntry,
    sensor_device: dr.DeviceEntry,
    sensor_entity_entry: er.RegistryEntry,
) -> None:
    """Test the source entity removed from the source device."""
    assert await hass.config_entries.async_setup(derivative_config_entry.entry_id)
    await hass.async_block_till_done()

    derivative_entity_entry = entity_registry.async_get("sensor.my_derivative")
    assert derivative_entity_entry.device_id == sensor_entity_entry.device_id

    sensor_device = device_registry.async_get(sensor_device.id)
    assert derivative_config_entry.entry_id not in sensor_device.config_entries

    events = track_entity_registry_actions(hass, derivative_entity_entry.entity_id)

    # Remove the source sensor from the device
    with patch(
        "homeassistant.components.derivative.async_unload_entry",
        wraps=derivative.async_unload_entry,
    ) as mock_unload_entry:
        entity_registry.async_update_entity(
            sensor_entity_entry.entity_id, device_id=None
        )
        await hass.async_block_till_done()
    mock_unload_entry.assert_called_once()

    # Check that the entity is no longer linked to the source device
    derivative_entity_entry = entity_registry.async_get("sensor.my_derivative")
    assert derivative_entity_entry.device_id is None

    # Check that the derivative config entry is not in the device
    sensor_device = device_registry.async_get(sensor_device.id)
    assert derivative_config_entry.entry_id not in sensor_device.config_entries

    # Check that the derivative config entry is not removed
    assert derivative_config_entry.entry_id in hass.config_entries.async_entry_ids()

    # Check we got the expected events
    assert events == ["update"]


async def test_async_handle_source_entity_changes_source_entity_moved_other_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    derivative_config_entry: MockConfigEntry,
    sensor_config_entry: ConfigEntry,
    sensor_device: dr.DeviceEntry,
    sensor_entity_entry: er.RegistryEntry,
) -> None:
    """Test the source entity is moved to another device."""
    sensor_device_2 = device_registry.async_get_or_create(
        config_entry_id=sensor_config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:FF")},
    )

    assert await hass.config_entries.async_setup(derivative_config_entry.entry_id)
    await hass.async_block_till_done()

    derivative_entity_entry = entity_registry.async_get("sensor.my_derivative")
    assert derivative_entity_entry.device_id == sensor_entity_entry.device_id

    sensor_device = device_registry.async_get(sensor_device.id)
    assert derivative_config_entry.entry_id not in sensor_device.config_entries
    sensor_device_2 = device_registry.async_get(sensor_device_2.id)
    assert derivative_config_entry.entry_id not in sensor_device_2.config_entries

    events = track_entity_registry_actions(hass, derivative_entity_entry.entity_id)

    # Move the source sensor to another device
    with patch(
        "homeassistant.components.derivative.async_unload_entry",
        wraps=derivative.async_unload_entry,
    ) as mock_unload_entry:
        entity_registry.async_update_entity(
            sensor_entity_entry.entity_id, device_id=sensor_device_2.id
        )
        await hass.async_block_till_done()
    mock_unload_entry.assert_called_once()

    # Check that the entity is linked to the other device
    derivative_entity_entry = entity_registry.async_get("sensor.my_derivative")
    assert derivative_entity_entry.device_id == sensor_device_2.id

    # Check that the derivative config entry is not in any of the devices
    sensor_device = device_registry.async_get(sensor_device.id)
    assert derivative_config_entry.entry_id not in sensor_device.config_entries
    sensor_device_2 = device_registry.async_get(sensor_device_2.id)
    assert derivative_config_entry.entry_id not in sensor_device_2.config_entries

    # Check that the derivative config entry is not removed
    assert derivative_config_entry.entry_id in hass.config_entries.async_entry_ids()

    # Check we got the expected events
    assert events == ["update"]


async def test_async_handle_source_entity_new_entity_id(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    derivative_config_entry: MockConfigEntry,
    sensor_device: dr.DeviceEntry,
    sensor_entity_entry: er.RegistryEntry,
) -> None:
    """Test the source entity's entity ID is changed."""
    assert await hass.config_entries.async_setup(derivative_config_entry.entry_id)
    await hass.async_block_till_done()

    derivative_entity_entry = entity_registry.async_get("sensor.my_derivative")
    assert derivative_entity_entry.device_id == sensor_entity_entry.device_id

    sensor_device = device_registry.async_get(sensor_device.id)
    assert derivative_config_entry.entry_id not in sensor_device.config_entries

    events = track_entity_registry_actions(hass, derivative_entity_entry.entity_id)

    # Change the source entity's entity ID
    with patch(
        "homeassistant.components.derivative.async_unload_entry",
        wraps=derivative.async_unload_entry,
    ) as mock_unload_entry:
        entity_registry.async_update_entity(
            sensor_entity_entry.entity_id, new_entity_id="sensor.new_entity_id"
        )
        await hass.async_block_till_done()
    mock_unload_entry.assert_called_once()

    # Check that the derivative config entry is updated with the new entity ID
    assert derivative_config_entry.options["source"] == "sensor.new_entity_id"

    # Check that the helper config is not in the device
    sensor_device = device_registry.async_get(sensor_device.id)
    assert derivative_config_entry.entry_id not in sensor_device.config_entries

    # Check that the derivative config entry is not removed
    assert derivative_config_entry.entry_id in hass.config_entries.async_entry_ids()

    # Check we got the expected events
    assert events == []


@pytest.mark.parametrize(
    ("unit_prefix", "expect_prefix"),
    [
        ({}, None),
        ({"unit_prefix": "k"}, "k"),
        ({"unit_prefix": "none"}, None),
    ],
)
async def test_migration_1_1(hass: HomeAssistant, unit_prefix, expect_prefix) -> None:
    """Test migration from v1.1 deletes "none" unit_prefix."""

    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "name": "My derivative",
            "round": 1.0,
            "source": "sensor.power",
            "time_window": {"seconds": 0.0},
            **unit_prefix,
            "unit_time": "min",
        },
        title="My derivative",
        version=1,
        minor_version=1,
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.options["unit_time"] == "min"
    assert config_entry.options.get("unit_prefix") == expect_prefix

    assert config_entry.version == 1
    assert config_entry.minor_version == 4


async def test_migration_1_2(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    sensor_device: dr.DeviceEntry,
    sensor_entity_entry: er.RegistryEntry,
) -> None:
    """Test migration from v1.2 removes derivative config entry from device."""

    derivative_config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "name": "My derivative",
            "round": 1.0,
            "source": "sensor.test_unique",
            "time_window": {"seconds": 0.0},
            "unit_prefix": "k",
            "unit_time": "min",
        },
        title="My derivative",
        version=1,
        minor_version=2,
    )
    derivative_config_entry.add_to_hass(hass)

    # Add the helper config entry to the device
    device_registry.async_update_device(
        sensor_device.id, add_config_entry_id=derivative_config_entry.entry_id
    )

    # Check preconditions
    sensor_device = device_registry.async_get(sensor_device.id)
    assert derivative_config_entry.entry_id in sensor_device.config_entries

    await hass.config_entries.async_setup(derivative_config_entry.entry_id)
    await hass.async_block_till_done()

    assert derivative_config_entry.state is ConfigEntryState.LOADED

    # Check that the helper config entry is removed from the device and the helper
    # entity is linked to the source device
    sensor_device = device_registry.async_get(sensor_device.id)
    assert derivative_config_entry.entry_id not in sensor_device.config_entries
    derivative_entity_entry = entity_registry.async_get("sensor.my_derivative")
    assert derivative_entity_entry.device_id == sensor_entity_entry.device_id

    assert derivative_config_entry.version == 1
    assert derivative_config_entry.minor_version == 4


@pytest.mark.parametrize(
    ("unit_prefix", "expect_prefix"),
    [
        ({"unit_prefix": "\u00b5"}, "\u03bc"),
        ({"unit_prefix": "\u03bc"}, "\u03bc"),
    ],
)
async def test_migration_1_4(hass: HomeAssistant, unit_prefix, expect_prefix) -> None:
    """Test migration from v1.4 migrates to Greek Mu char" unit_prefix."""

    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "name": "My derivative",
            "round": 1.0,
            "source": "sensor.power",
            "time_window": {"seconds": 0.0},
            **unit_prefix,
            "unit_time": "min",
        },
        title="My derivative",
        version=1,
        minor_version=1,
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.options["unit_time"] == "min"
    assert config_entry.options.get("unit_prefix") == expect_prefix

    assert config_entry.version == 1
    assert config_entry.minor_version == 4


async def test_migration_from_future_version(
    hass: HomeAssistant,
) -> None:
    """Test migration from future version."""

    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "name": "My derivative",
            "round": 1.0,
            "source": "sensor.power",
            "time_window": {"seconds": 0.0},
            "unit_prefix": "k",
            "unit_time": "min",
        },
        title="My derivative",
        version=2,
        minor_version=1,
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.MIGRATION_ERROR
