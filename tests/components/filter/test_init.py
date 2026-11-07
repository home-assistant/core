"""Test Filter component setup process."""

from unittest.mock import patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components import filter as filter_integration
from homeassistant.components.filter.const import FilterEntityStateAttribute
from homeassistant.components.recorder import Recorder
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_ENTITY_ID
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.event import async_track_entity_registry_updated_event

FILTER_ENTITY_ID = "sensor.mock_title_my_filter"


def track_entity_registry_actions(hass: HomeAssistant, entity_id: str) -> list[str]:
    """Track entity registry actions for an entity."""
    events = []

    @callback
    def add_event(event: Event[er.EventEntityRegistryUpdatedData]) -> None:
        """Add entity registry updated event to the list."""
        events.append(event.data["action"])

    async_track_entity_registry_updated_event(hass, entity_id, add_event)

    return events


async def test_unload_entry(
    recorder_mock: Recorder, hass: HomeAssistant, loaded_entry: MockConfigEntry
) -> None:
    """Test unload an entry."""

    assert loaded_entry.state is ConfigEntryState.LOADED
    assert await hass.config_entries.async_unload(loaded_entry.entry_id)
    await hass.async_block_till_done()
    assert loaded_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.usefixtures("recorder_mock")
async def test_async_handle_source_entity_changes_source_entity_removed(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    filter_config_entry: MockConfigEntry,
    sensor_device: dr.DeviceEntry,
    sensor_entity_entry: er.RegistryEntry,
) -> None:
    """Test the filter entity is detached when the source device is removed."""
    assert await hass.config_entries.async_setup(filter_config_entry.entry_id)
    await hass.async_block_till_done()

    filter_entity_entry = entity_registry.async_get(FILTER_ENTITY_ID)
    assert filter_entity_entry.device_id == sensor_entity_entry.device_id

    events = track_entity_registry_actions(hass, FILTER_ENTITY_ID)

    # Remove the source device, this removes the source sensor
    with patch(
        "homeassistant.components.filter.async_unload_entry",
        wraps=filter_integration.async_unload_entry,
    ) as mock_unload_entry:
        device_registry.async_remove_device(sensor_device.id)
        await hass.async_block_till_done()
        await hass.async_block_till_done()
    mock_unload_entry.assert_not_called()

    assert entity_registry.async_get(FILTER_ENTITY_ID).device_id is None
    assert not device_registry.async_get(sensor_device.id)
    assert filter_config_entry.entry_id in hass.config_entries.async_entry_ids()
    assert events == ["update"]


@pytest.mark.usefixtures("recorder_mock")
async def test_async_handle_source_entity_changes_source_entity_removed_shared_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    filter_config_entry: MockConfigEntry,
    sensor_device: dr.DeviceEntry,
    sensor_entity_entry: er.RegistryEntry,
) -> None:
    """Test the source device is kept when only the source entity is removed."""
    assert await hass.config_entries.async_setup(filter_config_entry.entry_id)
    await hass.async_block_till_done()

    filter_entity_entry = entity_registry.async_get(FILTER_ENTITY_ID)
    assert filter_entity_entry.device_id == sensor_entity_entry.device_id

    events = track_entity_registry_actions(hass, FILTER_ENTITY_ID)

    with patch(
        "homeassistant.components.filter.async_unload_entry",
        wraps=filter_integration.async_unload_entry,
    ) as mock_unload_entry:
        entity_registry.async_remove(sensor_entity_entry.entity_id)
        await hass.async_block_till_done()
        await hass.async_block_till_done()
    mock_unload_entry.assert_not_called()

    assert entity_registry.async_get(FILTER_ENTITY_ID).device_id is None
    sensor_device = device_registry.async_get(sensor_device.id)
    assert sensor_device is not None
    assert sensor_device.config_entry_id != filter_config_entry.entry_id
    assert filter_config_entry.entry_id in hass.config_entries.async_entry_ids()
    assert events == ["update"]


@pytest.mark.usefixtures("recorder_mock")
async def test_async_handle_source_entity_changes_source_entity_removed_from_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    filter_config_entry: MockConfigEntry,
    sensor_device: dr.DeviceEntry,
    sensor_entity_entry: er.RegistryEntry,
) -> None:
    """Test the source entity removed from the source device."""
    assert await hass.config_entries.async_setup(filter_config_entry.entry_id)
    await hass.async_block_till_done()

    filter_entity_entry = entity_registry.async_get(FILTER_ENTITY_ID)
    assert filter_entity_entry.device_id == sensor_entity_entry.device_id

    events = track_entity_registry_actions(hass, FILTER_ENTITY_ID)

    with patch(
        "homeassistant.components.filter.async_unload_entry",
        wraps=filter_integration.async_unload_entry,
    ) as mock_unload_entry:
        entity_registry.async_update_entity(
            sensor_entity_entry.entity_id, device_id=None
        )
        await hass.async_block_till_done()
    mock_unload_entry.assert_called_once()

    assert entity_registry.async_get(FILTER_ENTITY_ID).device_id is None
    sensor_device = device_registry.async_get(sensor_device.id)
    assert sensor_device.config_entry_id != filter_config_entry.entry_id
    assert filter_config_entry.entry_id in hass.config_entries.async_entry_ids()
    assert events == ["update"]


@pytest.mark.usefixtures("recorder_mock")
async def test_async_handle_source_entity_changes_source_entity_moved_other_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    filter_config_entry: MockConfigEntry,
    sensor_config_entry: ConfigEntry,
    sensor_device: dr.DeviceEntry,
    sensor_entity_entry: er.RegistryEntry,
) -> None:
    """Test the filter entity follows the source entity to another device."""
    sensor_device_2 = device_registry.async_get_or_create(
        config_entry_id=sensor_config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:FF")},
    )

    assert await hass.config_entries.async_setup(filter_config_entry.entry_id)
    await hass.async_block_till_done()

    filter_entity_entry = entity_registry.async_get(FILTER_ENTITY_ID)
    assert filter_entity_entry.device_id == sensor_entity_entry.device_id

    events = track_entity_registry_actions(hass, FILTER_ENTITY_ID)

    with patch(
        "homeassistant.components.filter.async_unload_entry",
        wraps=filter_integration.async_unload_entry,
    ) as mock_unload_entry:
        entity_registry.async_update_entity(
            sensor_entity_entry.entity_id, device_id=sensor_device_2.id
        )
        await hass.async_block_till_done()
    mock_unload_entry.assert_called_once()

    assert entity_registry.async_get(FILTER_ENTITY_ID).device_id == sensor_device_2.id
    sensor_device = device_registry.async_get(sensor_device.id)
    assert sensor_device.config_entry_id != filter_config_entry.entry_id
    sensor_device_2 = device_registry.async_get(sensor_device_2.id)
    assert sensor_device_2.config_entry_id != filter_config_entry.entry_id
    assert filter_config_entry.entry_id in hass.config_entries.async_entry_ids()
    assert events == ["update"]


@pytest.mark.usefixtures("recorder_mock")
async def test_async_handle_source_entity_new_entity_id(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    filter_config_entry: MockConfigEntry,
    sensor_entity_entry: er.RegistryEntry,
) -> None:
    """Test the source entity's entity ID is changed."""
    assert await hass.config_entries.async_setup(filter_config_entry.entry_id)
    await hass.async_block_till_done()

    filter_entity_entry = entity_registry.async_get(FILTER_ENTITY_ID)
    assert filter_entity_entry.device_id == sensor_entity_entry.device_id

    events = track_entity_registry_actions(hass, FILTER_ENTITY_ID)

    with patch(
        "homeassistant.components.filter.async_unload_entry",
        wraps=filter_integration.async_unload_entry,
    ) as mock_unload_entry:
        entity_registry.async_update_entity(
            sensor_entity_entry.entity_id, new_entity_id="sensor.new_entity_id"
        )
        await hass.async_block_till_done()
    mock_unload_entry.assert_called_once()

    assert filter_config_entry.options[CONF_ENTITY_ID] == "sensor.new_entity_id"
    assert (
        hass.states.get(FILTER_ENTITY_ID).attributes[
            FilterEntityStateAttribute.ENTITY_ID
        ]
        == "sensor.new_entity_id"
    )
    assert filter_config_entry.entry_id in hass.config_entries.async_entry_ids()
    assert events == []
