"""Test the Compensation integration setup."""

from unittest.mock import patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components import compensation
from homeassistant.components.compensation.const import (
    CONF_COMPENSATED_VALUE,
    CONF_UNCOMPENSATED_VALUE,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

ENTITY_ID = "sensor.my_compensation"


async def test_setup_and_unload_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test setting up and unloading a config entry."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    hass.states.async_set("sensor.uncompensated", "5")
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == "6.0"

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    "data_points",
    [
        [
            {CONF_UNCOMPENSATED_VALUE: 0.0, CONF_COMPENSATED_VALUE: 1.0},
            {CONF_UNCOMPENSATED_VALUE: 0.0, CONF_COMPENSATED_VALUE: 1.0},
        ]
    ],
)
async def test_setup_entry_polyfit_error(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test setup fails when no polynomial can be fitted to the data points."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert mock_config_entry.error_reason_translation_key == "setup_error"
    assert hass.states.get(ENTITY_ID) is None


async def test_source_entity_new_entity_id(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the config entry follows a renamed source entity."""
    source_entry = entity_registry.async_get_or_create(
        "sensor", "test", "unique", suggested_object_id="uncompensated"
    )
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_registry.async_update_entity(
        source_entry.entity_id, new_entity_id="sensor.new_entity_id"
    )
    await hass.async_block_till_done()

    assert mock_config_entry.options[CONF_ENTITY_ID] == "sensor.new_entity_id"
    assert mock_config_entry.state is ConfigEntryState.LOADED

    hass.states.async_set("sensor.new_entity_id", "5")
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == "6.0"


async def _setup_linked_entry(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    sensor_device: dr.DeviceEntry,
) -> str:
    """Set up the config entry and return the entity id linked to the source device."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        Platform.SENSOR, DOMAIN, mock_config_entry.entry_id
    )
    assert entity_id is not None
    assert entity_registry.async_get(entity_id).device_id == sensor_device.id
    return entity_id


async def test_source_entity_removed(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    sensor_device: dr.DeviceEntry,
    sensor_entity_entry: er.RegistryEntry,
) -> None:
    """Test the entity is detached from the device when the source entity is removed."""
    entity_id = await _setup_linked_entry(
        hass, entity_registry, mock_config_entry, sensor_device
    )

    with patch(
        "homeassistant.components.compensation.async_unload_entry",
        wraps=compensation.async_unload_entry,
    ) as mock_unload_entry:
        entity_registry.async_remove(sensor_entity_entry.entity_id)
        await hass.async_block_till_done()
    mock_unload_entry.assert_not_called()

    assert entity_registry.async_get(entity_id).device_id is None
    assert device_registry.async_get(sensor_device.id) is not None
    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_source_entity_removed_from_device(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    sensor_device: dr.DeviceEntry,
    sensor_entity_entry: er.RegistryEntry,
) -> None:
    """Test the entity is detached when the source entity leaves its device."""
    entity_id = await _setup_linked_entry(
        hass, entity_registry, mock_config_entry, sensor_device
    )

    with patch(
        "homeassistant.components.compensation.async_unload_entry",
        wraps=compensation.async_unload_entry,
    ) as mock_unload_entry:
        entity_registry.async_update_entity(
            sensor_entity_entry.entity_id, device_id=None
        )
        await hass.async_block_till_done()
    mock_unload_entry.assert_called_once()

    assert entity_registry.async_get(entity_id).device_id is None
    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_source_entity_moved_to_other_device(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    sensor_config_entry: MockConfigEntry,
    sensor_device: dr.DeviceEntry,
    sensor_entity_entry: er.RegistryEntry,
) -> None:
    """Test the entity follows the source entity to another device."""
    sensor_device_2 = device_registry.async_get_or_create(
        config_entry_id=sensor_config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:FF")},
    )
    entity_id = await _setup_linked_entry(
        hass, entity_registry, mock_config_entry, sensor_device
    )

    with patch(
        "homeassistant.components.compensation.async_unload_entry",
        wraps=compensation.async_unload_entry,
    ) as mock_unload_entry:
        entity_registry.async_update_entity(
            sensor_entity_entry.entity_id, device_id=sensor_device_2.id
        )
        await hass.async_block_till_done()
    mock_unload_entry.assert_called_once()

    assert entity_registry.async_get(entity_id).device_id == sensor_device_2.id
    assert mock_config_entry.state is ConfigEntryState.LOADED

    hass.states.async_set(sensor_entity_entry.entity_id, "5")
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "6.0"
