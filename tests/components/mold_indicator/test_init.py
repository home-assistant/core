"""Test Mold indicator component setup process."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from homeassistant.components import mold_indicator
from homeassistant.components.mold_indicator.config_flow import (
    MoldIndicatorConfigFlowHandler,
)
from homeassistant.components.mold_indicator.const import (
    CONF_CALIBRATION_FACTOR,
    CONF_INDOOR_HUMIDITY,
    CONF_INDOOR_TEMP,
    CONF_OUTDOOR_TEMP,
    DEFAULT_NAME,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_NAME
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.event import async_track_entity_registry_updated_event

from tests.common import MockConfigEntry


@pytest.fixture
def indoor_humidity_config_entry(hass: HomeAssistant) -> er.RegistryEntry:
    """Fixture to create a sensor config entry."""
    sensor_config_entry = MockConfigEntry()
    sensor_config_entry.add_to_hass(hass)
    return sensor_config_entry


@pytest.fixture
def indoor_humidity_device(
    device_registry: dr.DeviceRegistry, indoor_humidity_config_entry: ConfigEntry
) -> dr.DeviceEntry:
    """Fixture to create a sensor device."""
    return device_registry.async_get_or_create(
        config_entry_id=indoor_humidity_config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:ED")},
    )


@pytest.fixture
def indoor_humidity_entity_entry(
    entity_registry: er.EntityRegistry,
    indoor_humidity_config_entry: ConfigEntry,
    indoor_humidity_device: dr.DeviceEntry,
) -> er.RegistryEntry:
    """Fixture to create a sensor entity entry."""
    return entity_registry.async_get_or_create(
        "sensor",
        "test",
        "unique_indoor_humidity",
        config_entry=indoor_humidity_config_entry,
        device_id=indoor_humidity_device.id,
        original_name="ABC",
    )


@pytest.fixture
def indoor_temperature_config_entry(hass: HomeAssistant) -> er.RegistryEntry:
    """Fixture to create a sensor config entry."""
    sensor_config_entry = MockConfigEntry()
    sensor_config_entry.add_to_hass(hass)
    return sensor_config_entry


@pytest.fixture
def indoor_temperature_device(
    device_registry: dr.DeviceRegistry, indoor_temperature_config_entry: ConfigEntry
) -> dr.DeviceEntry:
    """Fixture to create a sensor device."""
    return device_registry.async_get_or_create(
        config_entry_id=indoor_temperature_config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EE")},
    )


@pytest.fixture
def indoor_temperature_entity_entry(
    entity_registry: er.EntityRegistry,
    indoor_temperature_config_entry: ConfigEntry,
    indoor_temperature_device: dr.DeviceEntry,
) -> er.RegistryEntry:
    """Fixture to create a sensor entity entry."""
    return entity_registry.async_get_or_create(
        "sensor",
        "test",
        "unique_indoor_temperature",
        config_entry=indoor_temperature_config_entry,
        device_id=indoor_temperature_device.id,
        original_name="ABC",
    )


@pytest.fixture
def outdoor_temperature_config_entry(hass: HomeAssistant) -> er.RegistryEntry:
    """Fixture to create a sensor config entry."""
    sensor_config_entry = MockConfigEntry()
    sensor_config_entry.add_to_hass(hass)
    return sensor_config_entry


@pytest.fixture
def outdoor_temperature_device(
    device_registry: dr.DeviceRegistry, outdoor_temperature_config_entry: ConfigEntry
) -> dr.DeviceEntry:
    """Fixture to create a sensor device."""
    return device_registry.async_get_or_create(
        config_entry_id=outdoor_temperature_config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )


@pytest.fixture
def outdoor_temperature_entity_entry(
    entity_registry: er.EntityRegistry,
    outdoor_temperature_config_entry: ConfigEntry,
    outdoor_temperature_device: dr.DeviceEntry,
) -> er.RegistryEntry:
    """Fixture to create a sensor entity entry."""
    return entity_registry.async_get_or_create(
        "sensor",
        "test",
        "unique_outdoor_temperature",
        config_entry=outdoor_temperature_config_entry,
        device_id=outdoor_temperature_device.id,
        original_name="ABC",
    )


@pytest.fixture
def mold_indicator_config_entry(
    hass: HomeAssistant,
    indoor_humidity_entity_entry: er.RegistryEntry,
    indoor_temperature_entity_entry: er.RegistryEntry,
    outdoor_temperature_entity_entry: er.RegistryEntry,
) -> MockConfigEntry:
    """Fixture to create a mold_indicator config entry."""
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            CONF_NAME: "My mold indicator",
            CONF_INDOOR_HUMIDITY: indoor_humidity_entity_entry.entity_id,
            CONF_INDOOR_TEMP: indoor_temperature_entity_entry.entity_id,
            CONF_OUTDOOR_TEMP: outdoor_temperature_entity_entry.entity_id,
            CONF_CALIBRATION_FACTOR: 2.0,
        },
        title="My mold indicator",
        version=MoldIndicatorConfigFlowHandler.VERSION,
        minor_version=MoldIndicatorConfigFlowHandler.MINOR_VERSION,
    )

    config_entry.add_to_hass(hass)

    return config_entry


@pytest.fixture
def expected_helper_device_id(
    request: pytest.FixtureRequest,
    indoor_humidity_device: dr.DeviceEntry,
) -> str | None:
    """Fixture to provide the expected helper device ID."""
    return indoor_humidity_device.id if request.param == "humidity_device_id" else None


def track_entity_registry_actions(hass: HomeAssistant, entity_id: str) -> list[str]:
    """Track entity registry actions for an entity."""
    events = []

    @callback
    def add_event(event: Event[er.EventEntityRegistryUpdatedData]) -> None:
        """Add entity registry updated event to the list."""
        events.append(event.data["action"])

    async_track_entity_registry_updated_event(hass, entity_id, add_event)

    return events


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
    """Test cleaning of devices linked to the helper config entry."""

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
        "indoor",
        "humidity",
        config_entry=source_config_entry,
        device_id=source_device1_entry.id,
    )
    await hass.async_block_till_done()
    assert entity_registry.async_get("sensor.indoor_humidity") is not None

    # Configure the configuration entry for helper
    helper_config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            CONF_NAME: DEFAULT_NAME,
            CONF_INDOOR_HUMIDITY: "sensor.indoor_humidity",
            CONF_INDOOR_TEMP: "sensor.indoor_temp",
            CONF_OUTDOOR_TEMP: "sensor.outdoor_temp",
            CONF_CALIBRATION_FACTOR: 2.0,
        },
        title="Test",
    )
    helper_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(helper_config_entry.entry_id)
    await hass.async_block_till_done()

    # Confirm the link between the source entity device and the helper entity
    helper_entity = entity_registry.async_get("sensor.mold_indicator")
    assert helper_entity is not None
    assert helper_entity.device_id == source_entity.device_id

    # Device entry incorrectly linked to config entry
    device_registry.async_get_or_create(
        config_entry_id=helper_config_entry.entry_id,
        identifiers={("sensor", "identifier_test2")},
        connections={("mac", "30:31:32:33:34:02")},
    )
    device_registry.async_get_or_create(
        config_entry_id=helper_config_entry.entry_id,
        identifiers={("sensor", "identifier_test3")},
        connections={("mac", "30:31:32:33:34:03")},
    )
    await hass.async_block_till_done()

    # Before reloading the config entry, 3 devices are expected to be linked
    devices_before_reload = device_registry.devices.get_devices_for_config_entry_id(
        helper_config_entry.entry_id
    )
    assert len(devices_before_reload) == 2

    # Config entry reload
    await hass.config_entries.async_reload(helper_config_entry.entry_id)
    await hass.async_block_till_done()

    # Confirm the link between the source entity device and the helper entity
    helper_entity = entity_registry.async_get("sensor.mold_indicator")
    assert helper_entity is not None
    assert helper_entity.device_id == source_entity.device_id

    # After reloading the config entry, only one linked device is expected
    devices_after_reload = device_registry.devices.get_devices_for_config_entry_id(
        helper_config_entry.entry_id
    )
    assert len(devices_after_reload) == 0


@pytest.mark.parametrize(
    ("source_entity_id", "expected_helper_device_id", "expected_events"),
    [
        ("sensor.test_unique_indoor_humidity", None, ["update"]),
        ("sensor.test_unique_indoor_temperature", "humidity_device_id", []),
        ("sensor.test_unique_outdoor_temperature", "humidity_device_id", []),
    ],
    indirect=["expected_helper_device_id"],
)
async def test_async_handle_source_entity_changes_source_entity_removed(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mold_indicator_config_entry: MockConfigEntry,
    indoor_humidity_entity_entry: er.RegistryEntry,
    source_entity_id: str,
    expected_helper_device_id: str | None,
    expected_events: list[str],
) -> None:
    """Test the mold_indicator config entry is removed when the source entity is removed."""
    source_entity_entry = entity_registry.async_get(source_entity_id)

    assert await hass.config_entries.async_setup(mold_indicator_config_entry.entry_id)
    await hass.async_block_till_done()

    mold_indicator_entity_entry = entity_registry.async_get("sensor.my_mold_indicator")
    assert (
        mold_indicator_entity_entry.device_id == indoor_humidity_entity_entry.device_id
    )

    source_device = device_registry.async_get(source_entity_entry.device_id)
    assert mold_indicator_config_entry.entry_id not in source_device.config_entries

    events = track_entity_registry_actions(hass, mold_indicator_entity_entry.entity_id)

    # Remove the source entity's config entry from the device, this removes the
    # source entity
    with patch(
        "homeassistant.components.mold_indicator.async_unload_entry",
        wraps=mold_indicator.async_unload_entry,
    ) as mock_unload_entry:
        device_registry.async_update_device(
            source_device.id, remove_config_entry_id=source_entity_entry.config_entry_id
        )
        await hass.async_block_till_done()
        await hass.async_block_till_done()
    mock_unload_entry.assert_not_called()

    # Check that the helper entity is linked to the expected source device
    mold_indicator_entity_entry = entity_registry.async_get("sensor.my_mold_indicator")
    assert mold_indicator_entity_entry.device_id == expected_helper_device_id

    # Check that the device is removed
    assert not device_registry.async_get(source_device.id)

    # Check that the mold_indicator config entry is not removed
    assert mold_indicator_config_entry.entry_id in hass.config_entries.async_entry_ids()

    # Check we got the expected events
    assert events == expected_events


@pytest.mark.parametrize(
    ("source_entity_id", "expected_helper_device_id", "expected_events"),
    [
        ("sensor.test_unique_indoor_humidity", None, ["update"]),
        ("sensor.test_unique_indoor_temperature", "humidity_device_id", []),
        ("sensor.test_unique_outdoor_temperature", "humidity_device_id", []),
    ],
    indirect=["expected_helper_device_id"],
)
async def test_async_handle_source_entity_changes_source_entity_removed_shared_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mold_indicator_config_entry: MockConfigEntry,
    indoor_humidity_entity_entry: er.RegistryEntry,
    source_entity_id: str,
    expected_helper_device_id: str | None,
    expected_events: list[str],
) -> None:
    """Test the mold_indicator config entry is removed when the source entity is removed."""
    source_entity_entry = entity_registry.async_get(source_entity_id)

    # Add another config entry to the source device
    other_config_entry = MockConfigEntry()
    other_config_entry.add_to_hass(hass)
    device_registry.async_update_device(
        source_entity_entry.device_id, add_config_entry_id=other_config_entry.entry_id
    )

    assert await hass.config_entries.async_setup(mold_indicator_config_entry.entry_id)
    await hass.async_block_till_done()

    mold_indicator_entity_entry = entity_registry.async_get("sensor.my_mold_indicator")
    assert (
        mold_indicator_entity_entry.device_id == indoor_humidity_entity_entry.device_id
    )

    source_device = device_registry.async_get(source_entity_entry.device_id)
    assert mold_indicator_config_entry.entry_id not in source_device.config_entries

    events = track_entity_registry_actions(hass, mold_indicator_entity_entry.entity_id)

    # Remove the source entity's config entry from the device, this removes the
    # source entity
    with patch(
        "homeassistant.components.mold_indicator.async_unload_entry",
        wraps=mold_indicator.async_unload_entry,
    ) as mock_unload_entry:
        device_registry.async_update_device(
            source_device.id, remove_config_entry_id=source_entity_entry.config_entry_id
        )
        await hass.async_block_till_done()
        await hass.async_block_till_done()
    mock_unload_entry.assert_not_called()

    # Check that the helper entity is linked to the expected source device
    mold_indicator_entity_entry = entity_registry.async_get("sensor.my_mold_indicator")
    assert mold_indicator_entity_entry.device_id == expected_helper_device_id

    # Check if the mold_indicator config entry is not in the device
    source_device = device_registry.async_get(source_device.id)
    assert mold_indicator_config_entry.entry_id not in source_device.config_entries

    # Check that the mold_indicator config entry is not removed
    assert mold_indicator_config_entry.entry_id in hass.config_entries.async_entry_ids()

    # Check we got the expected events
    assert events == expected_events


@pytest.mark.parametrize(
    (
        "source_entity_id",
        "unload_entry_calls",
        "expected_helper_device_id",
        "expected_events",
    ),
    [
        ("sensor.test_unique_indoor_humidity", 1, None, ["update"]),
        ("sensor.test_unique_indoor_temperature", 0, "humidity_device_id", []),
        ("sensor.test_unique_outdoor_temperature", 0, "humidity_device_id", []),
    ],
    indirect=["expected_helper_device_id"],
)
async def test_async_handle_source_entity_changes_source_entity_removed_from_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mold_indicator_config_entry: MockConfigEntry,
    indoor_humidity_entity_entry: er.RegistryEntry,
    source_entity_id: str,
    unload_entry_calls: int,
    expected_helper_device_id: str | None,
    expected_events: list[str],
) -> None:
    """Test the source entity removed from the source device."""
    source_entity_entry = entity_registry.async_get(source_entity_id)

    assert await hass.config_entries.async_setup(mold_indicator_config_entry.entry_id)
    await hass.async_block_till_done()

    mold_indicator_entity_entry = entity_registry.async_get("sensor.my_mold_indicator")
    assert (
        mold_indicator_entity_entry.device_id == indoor_humidity_entity_entry.device_id
    )

    source_device = device_registry.async_get(source_entity_entry.device_id)
    assert mold_indicator_config_entry.entry_id not in source_device.config_entries

    events = track_entity_registry_actions(hass, mold_indicator_entity_entry.entity_id)

    # Remove the source entity from the device
    with patch(
        "homeassistant.components.mold_indicator.async_unload_entry",
        wraps=mold_indicator.async_unload_entry,
    ) as mock_unload_entry:
        entity_registry.async_update_entity(
            source_entity_entry.entity_id, device_id=None
        )
        await hass.async_block_till_done()
    assert len(mock_unload_entry.mock_calls) == unload_entry_calls

    # Check that the helper entity is linked to the expected source device
    mold_indicator_entity_entry = entity_registry.async_get("sensor.my_mold_indicator")
    assert mold_indicator_entity_entry.device_id == expected_helper_device_id

    # Check that the mold_indicator config entry is not in the device
    source_device = device_registry.async_get(source_device.id)
    assert mold_indicator_config_entry.entry_id not in source_device.config_entries

    # Check that the mold_indicator config entry is not removed
    assert mold_indicator_config_entry.entry_id in hass.config_entries.async_entry_ids()

    # Check we got the expected events
    assert events == expected_events


@pytest.mark.parametrize(
    ("source_entity_id", "unload_entry_calls", "expected_events"),
    [
        ("sensor.test_unique_indoor_humidity", 1, ["update"]),
        ("sensor.test_unique_indoor_temperature", 0, []),
        ("sensor.test_unique_outdoor_temperature", 0, []),
    ],
)
async def test_async_handle_source_entity_changes_source_entity_moved_other_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mold_indicator_config_entry: MockConfigEntry,
    indoor_humidity_entity_entry: er.RegistryEntry,
    source_entity_id: str,
    unload_entry_calls: int,
    expected_events: list[str],
) -> None:
    """Test the source entity is moved to another device."""
    source_entity_entry = entity_registry.async_get(source_entity_id)

    source_device_2 = device_registry.async_get_or_create(
        config_entry_id=source_entity_entry.config_entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:FF")},
    )

    assert await hass.config_entries.async_setup(mold_indicator_config_entry.entry_id)
    await hass.async_block_till_done()

    mold_indicator_entity_entry = entity_registry.async_get("sensor.my_mold_indicator")
    assert (
        mold_indicator_entity_entry.device_id == indoor_humidity_entity_entry.device_id
    )

    source_device = device_registry.async_get(source_entity_entry.device_id)
    assert mold_indicator_config_entry.entry_id not in source_device.config_entries
    source_device_2 = device_registry.async_get(source_device_2.id)
    assert mold_indicator_config_entry.entry_id not in source_device_2.config_entries

    events = track_entity_registry_actions(hass, mold_indicator_entity_entry.entity_id)

    # Move the source entity to another device
    with patch(
        "homeassistant.components.mold_indicator.async_unload_entry",
        wraps=mold_indicator.async_unload_entry,
    ) as mock_unload_entry:
        entity_registry.async_update_entity(
            source_entity_entry.entity_id, device_id=source_device_2.id
        )
        await hass.async_block_till_done()
    assert len(mock_unload_entry.mock_calls) == unload_entry_calls

    # Check that the helper entity is linked to the expected source device
    indoor_humidity_entity_entry = entity_registry.async_get(
        indoor_humidity_entity_entry.entity_id
    )
    mold_indicator_entity_entry = entity_registry.async_get("sensor.my_mold_indicator")
    assert (
        mold_indicator_entity_entry.device_id == indoor_humidity_entity_entry.device_id
    )

    # Check that the mold_indicator config entry is not in any of the devices
    source_device = device_registry.async_get(source_device.id)
    assert mold_indicator_config_entry.entry_id not in source_device.config_entries
    source_device_2 = device_registry.async_get(source_device_2.id)
    assert mold_indicator_config_entry.entry_id not in source_device_2.config_entries

    # Check that the mold_indicator config entry is not removed
    assert mold_indicator_config_entry.entry_id in hass.config_entries.async_entry_ids()

    # Check we got the expected events
    assert events == expected_events


@pytest.mark.parametrize(
    ("source_entity_id", "config_key"),
    [
        ("sensor.test_unique_indoor_humidity", CONF_INDOOR_HUMIDITY),
        ("sensor.test_unique_indoor_temperature", CONF_INDOOR_TEMP),
        ("sensor.test_unique_outdoor_temperature", CONF_OUTDOOR_TEMP),
    ],
)
async def test_async_handle_source_entity_new_entity_id(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mold_indicator_config_entry: MockConfigEntry,
    indoor_humidity_entity_entry: er.RegistryEntry,
    source_entity_id: str,
    config_key: str,
) -> None:
    """Test the source entity's entity ID is changed."""
    source_entity_entry = entity_registry.async_get(source_entity_id)

    assert await hass.config_entries.async_setup(mold_indicator_config_entry.entry_id)
    await hass.async_block_till_done()

    mold_indicator_entity_entry = entity_registry.async_get("sensor.my_mold_indicator")
    assert (
        mold_indicator_entity_entry.device_id == indoor_humidity_entity_entry.device_id
    )

    source_device = device_registry.async_get(source_entity_entry.device_id)
    assert mold_indicator_config_entry.entry_id not in source_device.config_entries

    events = track_entity_registry_actions(hass, mold_indicator_entity_entry.entity_id)

    # Change the source entity's entity ID
    with patch(
        "homeassistant.components.mold_indicator.async_unload_entry",
        wraps=mold_indicator.async_unload_entry,
    ) as mock_unload_entry:
        entity_registry.async_update_entity(
            source_entity_entry.entity_id, new_entity_id="sensor.new_entity_id"
        )
        await hass.async_block_till_done()
    mock_unload_entry.assert_called_once()

    # Check that the mold_indicator config entry is updated with the new entity ID
    assert mold_indicator_config_entry.options[config_key] == "sensor.new_entity_id"

    # Check that the helper config is not in the device
    source_device = device_registry.async_get(source_device.id)
    assert mold_indicator_config_entry.entry_id not in source_device.config_entries

    # Check that the mold_indicator config entry is not removed
    assert mold_indicator_config_entry.entry_id in hass.config_entries.async_entry_ids()

    # Check we got the expected events
    assert events == []


async def test_migration_1_1(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    indoor_humidity_device: dr.DeviceEntry,
    indoor_humidity_entity_entry: er.RegistryEntry,
    indoor_temperature_entity_entry: er.RegistryEntry,
    outdoor_temperature_entity_entry: er.RegistryEntry,
) -> None:
    """Test migration from v1.1 removes mold_indicator config entry from device."""

    mold_indicator_config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            CONF_NAME: "My mold indicator",
            CONF_INDOOR_HUMIDITY: indoor_humidity_entity_entry.entity_id,
            CONF_INDOOR_TEMP: indoor_temperature_entity_entry.entity_id,
            CONF_OUTDOOR_TEMP: outdoor_temperature_entity_entry.entity_id,
            CONF_CALIBRATION_FACTOR: 2.0,
        },
        title="My mold indicator",
        version=1,
        minor_version=1,
    )
    mold_indicator_config_entry.add_to_hass(hass)

    # Add the helper config entry to the device
    device_registry.async_update_device(
        indoor_humidity_device.id,
        add_config_entry_id=mold_indicator_config_entry.entry_id,
    )

    # Check preconditions
    switch_device = device_registry.async_get(indoor_humidity_device.id)
    assert mold_indicator_config_entry.entry_id in switch_device.config_entries

    await hass.config_entries.async_setup(mold_indicator_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mold_indicator_config_entry.state is ConfigEntryState.LOADED

    # Check that the helper config entry is removed from the device and the helper
    # entity is linked to the source device
    switch_device = device_registry.async_get(switch_device.id)
    assert mold_indicator_config_entry.entry_id not in switch_device.config_entries
    mold_indicator_entity_entry = entity_registry.async_get("sensor.my_mold_indicator")
    assert (
        mold_indicator_entity_entry.device_id == indoor_humidity_entity_entry.device_id
    )

    assert mold_indicator_config_entry.version == 1
    assert mold_indicator_config_entry.minor_version == 2


async def test_migration_from_future_version(
    hass: HomeAssistant,
) -> None:
    """Test migration from future version."""
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            CONF_NAME: DEFAULT_NAME,
            CONF_INDOOR_HUMIDITY: "sensor.indoor_humidity",
            CONF_INDOOR_TEMP: "sensor.indoor_temp",
            CONF_OUTDOOR_TEMP: "sensor.outdoor_temp",
            CONF_CALIBRATION_FACTOR: 2.0,
        },
        title="My mold indicator",
        version=2,
        minor_version=1,
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.MIGRATION_ERROR
