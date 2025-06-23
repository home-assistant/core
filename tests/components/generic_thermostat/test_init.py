"""Test Generic Thermostat component setup process."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from homeassistant.components import generic_thermostat
from homeassistant.components.generic_thermostat.config_flow import ConfigFlowHandler
from homeassistant.components.generic_thermostat.const import DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant
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
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EE")},
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
def switch_config_entry(hass: HomeAssistant) -> er.RegistryEntry:
    """Fixture to create a switch config entry."""
    switch_config_entry = MockConfigEntry()
    switch_config_entry.add_to_hass(hass)
    return switch_config_entry


@pytest.fixture
def switch_device(
    device_registry: dr.DeviceRegistry, switch_config_entry: ConfigEntry
) -> dr.DeviceEntry:
    """Fixture to create a switch device."""
    return device_registry.async_get_or_create(
        config_entry_id=switch_config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )


@pytest.fixture
def switch_entity_entry(
    entity_registry: er.EntityRegistry,
    switch_config_entry: ConfigEntry,
    switch_device: dr.DeviceEntry,
) -> er.RegistryEntry:
    """Fixture to create a switch entity entry."""
    return entity_registry.async_get_or_create(
        "switch",
        "test",
        "unique",
        config_entry=switch_config_entry,
        device_id=switch_device.id,
        original_name="ABC",
    )


@pytest.fixture
def generic_thermostat_config_entry(
    hass: HomeAssistant,
    sensor_entity_entry: er.RegistryEntry,
    switch_entity_entry: er.RegistryEntry,
) -> MockConfigEntry:
    """Fixture to create a generic_thermostat config entry."""
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "name": "My generic thermostat",
            "heater": switch_entity_entry.entity_id,
            "target_sensor": sensor_entity_entry.entity_id,
            "ac_mode": False,
            "cold_tolerance": 0.3,
            "hot_tolerance": 0.3,
        },
        title="My generic thermostat",
        version=ConfigFlowHandler.VERSION,
        minor_version=ConfigFlowHandler.MINOR_VERSION,
    )

    config_entry.add_to_hass(hass)

    return config_entry


def track_entity_registry_actions(hass: HomeAssistant, entity_id: str) -> list[str]:
    """Track entity registry actions for an entity."""
    events = []

    def add_event(event: Event[er.EventEntityRegistryUpdatedData]) -> None:
        """Add entity registry updated event to the list."""
        events.append(event.data["action"])

    async_track_entity_registry_updated_event(hass, entity_id, add_event)

    return events


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
        identifiers={("switch", "identifier_test1")},
        connections={("mac", "30:31:32:33:34:01")},
    )

    # Source entity registry
    source_entity = entity_registry.async_get_or_create(
        "switch",
        "test",
        "source",
        config_entry=source_config_entry,
        device_id=source_device1_entry.id,
    )
    await hass.async_block_till_done()
    assert entity_registry.async_get("switch.test_source") is not None

    # Configure the configuration entry for helper
    helper_config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "name": "Test",
            "heater": "switch.test_source",
            "target_sensor": "sensor.temperature",
            "ac_mode": False,
            "cold_tolerance": 0.3,
            "hot_tolerance": 0.3,
        },
        title="Test",
    )
    helper_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(helper_config_entry.entry_id)
    await hass.async_block_till_done()

    # Confirm the link between the source entity device and the helper entity
    helper_entity = entity_registry.async_get("climate.test")
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
    assert len(devices_before_reload) == 3

    # Config entry reload
    await hass.config_entries.async_reload(helper_config_entry.entry_id)
    await hass.async_block_till_done()

    # Confirm the link between the source entity device and the helper entity
    helper_entity = entity_registry.async_get("climate.test")
    assert helper_entity is not None
    assert helper_entity.device_id == source_entity.device_id

    # After reloading the config entry, only one linked device is expected
    devices_after_reload = device_registry.devices.get_devices_for_config_entry_id(
        helper_config_entry.entry_id
    )
    assert len(devices_after_reload) == 1

    assert devices_after_reload[0].id == source_device1_entry.id


@pytest.mark.usefixtures(
    "sensor_config_entry",
    "sensor_device",
    "sensor_entity_entry",
    "switch_config_entry",
    "switch_device",
)
@pytest.mark.parametrize(
    ("source_entity_id", "helper_in_device", "expected_events"),
    [("switch.test_unique", True, ["update"]), ("sensor.test_unique", False, [])],
)
async def test_async_handle_source_entity_changes_source_entity_removed(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    generic_thermostat_config_entry: MockConfigEntry,
    switch_entity_entry: er.RegistryEntry,
    source_entity_id: str,
    helper_in_device: bool,
    expected_events: list[str],
) -> None:
    """Test the generic_thermostat config entry is removed when the source entity is removed."""
    source_entity_entry = entity_registry.async_get(source_entity_id)

    # Add another config entry to the source device
    other_config_entry = MockConfigEntry()
    other_config_entry.add_to_hass(hass)
    device_registry.async_update_device(
        source_entity_entry.device_id, add_config_entry_id=other_config_entry.entry_id
    )

    assert await hass.config_entries.async_setup(
        generic_thermostat_config_entry.entry_id
    )
    await hass.async_block_till_done()

    generic_thermostat_entity_entry = entity_registry.async_get(
        "climate.my_generic_thermostat"
    )
    assert generic_thermostat_entity_entry.device_id == switch_entity_entry.device_id

    source_device = device_registry.async_get(source_entity_entry.device_id)
    assert (
        generic_thermostat_config_entry.entry_id in source_device.config_entries
    ) == helper_in_device

    events = track_entity_registry_actions(
        hass, generic_thermostat_entity_entry.entity_id
    )

    # Remove the source entity's config entry from the device, this removes the
    # source entity
    with patch(
        "homeassistant.components.generic_thermostat.async_unload_entry",
        wraps=generic_thermostat.async_unload_entry,
    ) as mock_unload_entry:
        device_registry.async_update_device(
            source_device.id, remove_config_entry_id=source_entity_entry.config_entry_id
        )
        await hass.async_block_till_done()
        await hass.async_block_till_done()
    mock_unload_entry.assert_not_called()

    # Check if the generic_thermostat config entry is not in the device
    source_device = device_registry.async_get(source_device.id)
    assert generic_thermostat_config_entry.entry_id not in source_device.config_entries

    # Check that the generic_thermostat config entry is not removed
    assert (
        generic_thermostat_config_entry.entry_id
        in hass.config_entries.async_entry_ids()
    )

    # Check we got the expected events
    assert events == expected_events


@pytest.mark.usefixtures(
    "sensor_config_entry",
    "sensor_device",
    "sensor_entity_entry",
    "switch_config_entry",
    "switch_device",
)
@pytest.mark.parametrize(
    ("source_entity_id", "helper_in_device", "unload_entry_calls", "expected_events"),
    [("switch.test_unique", True, 1, ["update"]), ("sensor.test_unique", False, 0, [])],
)
async def test_async_handle_source_entity_changes_source_entity_removed_from_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    generic_thermostat_config_entry: MockConfigEntry,
    switch_entity_entry: er.RegistryEntry,
    source_entity_id: str,
    helper_in_device: bool,
    unload_entry_calls: int,
    expected_events: list[str],
) -> None:
    """Test the source entity removed from the source device."""
    source_entity_entry = entity_registry.async_get(source_entity_id)

    assert await hass.config_entries.async_setup(
        generic_thermostat_config_entry.entry_id
    )
    await hass.async_block_till_done()

    generic_thermostat_entity_entry = entity_registry.async_get(
        "climate.my_generic_thermostat"
    )
    assert generic_thermostat_entity_entry.device_id == switch_entity_entry.device_id

    source_device = device_registry.async_get(source_entity_entry.device_id)
    assert (
        generic_thermostat_config_entry.entry_id in source_device.config_entries
    ) == helper_in_device

    events = track_entity_registry_actions(
        hass, generic_thermostat_entity_entry.entity_id
    )

    # Remove the source entity from the device
    with patch(
        "homeassistant.components.generic_thermostat.async_unload_entry",
        wraps=generic_thermostat.async_unload_entry,
    ) as mock_unload_entry:
        entity_registry.async_update_entity(
            source_entity_entry.entity_id, device_id=None
        )
        await hass.async_block_till_done()
    assert len(mock_unload_entry.mock_calls) == unload_entry_calls

    # Check that the generic_thermostat config entry is removed from the device
    source_device = device_registry.async_get(source_device.id)
    assert generic_thermostat_config_entry.entry_id not in source_device.config_entries

    # Check that the generic_thermostat config entry is not removed
    assert (
        generic_thermostat_config_entry.entry_id
        in hass.config_entries.async_entry_ids()
    )

    # Check we got the expected events
    assert events == expected_events


@pytest.mark.usefixtures(
    "sensor_config_entry",
    "sensor_device",
    "sensor_entity_entry",
    "switch_config_entry",
    "switch_device",
)
@pytest.mark.parametrize(
    ("source_entity_id", "helper_in_device", "unload_entry_calls", "expected_events"),
    [("switch.test_unique", True, 1, ["update"]), ("sensor.test_unique", False, 0, [])],
)
async def test_async_handle_source_entity_changes_source_entity_moved_other_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    generic_thermostat_config_entry: MockConfigEntry,
    switch_entity_entry: er.RegistryEntry,
    source_entity_id: str,
    helper_in_device: bool,
    unload_entry_calls: int,
    expected_events: list[str],
) -> None:
    """Test the source entity is moved to another device."""
    source_entity_entry = entity_registry.async_get(source_entity_id)

    source_device_2 = device_registry.async_get_or_create(
        config_entry_id=source_entity_entry.config_entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:FF")},
    )

    assert await hass.config_entries.async_setup(
        generic_thermostat_config_entry.entry_id
    )
    await hass.async_block_till_done()

    generic_thermostat_entity_entry = entity_registry.async_get(
        "climate.my_generic_thermostat"
    )
    assert generic_thermostat_entity_entry.device_id == switch_entity_entry.device_id

    source_device = device_registry.async_get(source_entity_entry.device_id)
    assert (
        generic_thermostat_config_entry.entry_id in source_device.config_entries
    ) == helper_in_device
    source_device_2 = device_registry.async_get(source_device_2.id)
    assert (
        generic_thermostat_config_entry.entry_id not in source_device_2.config_entries
    )

    events = track_entity_registry_actions(
        hass, generic_thermostat_entity_entry.entity_id
    )

    # Move the source entity to another device
    with patch(
        "homeassistant.components.generic_thermostat.async_unload_entry",
        wraps=generic_thermostat.async_unload_entry,
    ) as mock_unload_entry:
        entity_registry.async_update_entity(
            source_entity_entry.entity_id, device_id=source_device_2.id
        )
        await hass.async_block_till_done()
    assert len(mock_unload_entry.mock_calls) == unload_entry_calls

    # Check that the generic_thermostat config entry is moved to the other device
    source_device = device_registry.async_get(source_device.id)
    assert generic_thermostat_config_entry.entry_id not in source_device.config_entries
    source_device_2 = device_registry.async_get(source_device_2.id)
    assert (
        generic_thermostat_config_entry.entry_id in source_device_2.config_entries
    ) == helper_in_device

    # Check that the generic_thermostat config entry is not removed
    assert (
        generic_thermostat_config_entry.entry_id
        in hass.config_entries.async_entry_ids()
    )

    # Check we got the expected events
    assert events == expected_events


@pytest.mark.usefixtures(
    "sensor_config_entry",
    "sensor_device",
    "sensor_entity_entry",
    "switch_config_entry",
    "switch_device",
)
@pytest.mark.parametrize(
    ("source_entity_id", "new_entity_id", "helper_in_device", "config_key"),
    [
        ("switch.test_unique", "switch.new_entity_id", True, "heater"),
        ("sensor.test_unique", "sensor.new_entity_id", False, "target_sensor"),
    ],
)
async def test_async_handle_source_entity_new_entity_id(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    generic_thermostat_config_entry: MockConfigEntry,
    switch_entity_entry: er.RegistryEntry,
    source_entity_id: str,
    new_entity_id: str,
    helper_in_device: bool,
    config_key: str,
) -> None:
    """Test the source entity's entity ID is changed."""
    source_entity_entry = entity_registry.async_get(source_entity_id)

    assert await hass.config_entries.async_setup(
        generic_thermostat_config_entry.entry_id
    )
    await hass.async_block_till_done()

    generic_thermostat_entity_entry = entity_registry.async_get(
        "climate.my_generic_thermostat"
    )
    assert generic_thermostat_entity_entry.device_id == switch_entity_entry.device_id

    source_device = device_registry.async_get(source_entity_entry.device_id)
    assert (
        generic_thermostat_config_entry.entry_id in source_device.config_entries
    ) == helper_in_device

    events = track_entity_registry_actions(
        hass, generic_thermostat_entity_entry.entity_id
    )

    # Change the source entity's entity ID
    with patch(
        "homeassistant.components.generic_thermostat.async_unload_entry",
        wraps=generic_thermostat.async_unload_entry,
    ) as mock_unload_entry:
        entity_registry.async_update_entity(
            source_entity_entry.entity_id, new_entity_id=new_entity_id
        )
        await hass.async_block_till_done()
    mock_unload_entry.assert_called_once()

    # Check that the generic_thermostat config entry is updated with the new entity ID
    assert generic_thermostat_config_entry.options[config_key] == new_entity_id

    # Check that the helper config is still in the device
    source_device = device_registry.async_get(source_device.id)
    assert (
        generic_thermostat_config_entry.entry_id in source_device.config_entries
    ) == helper_in_device

    # Check that the generic_thermostat config entry is not removed
    assert (
        generic_thermostat_config_entry.entry_id
        in hass.config_entries.async_entry_ids()
    )

    # Check we got the expected events
    assert events == []
