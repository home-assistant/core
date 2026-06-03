"""Tests for the OPNsense sensor platform."""

import pytest

from homeassistant.components import sensor
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.entity_registry import RegistryEntryDisabler

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_opnsense_client")
async def test_sensor_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test sensor platform setup."""
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    sensor_entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    sensor_entities = [
        entity for entity in sensor_entities if entity.domain == sensor.DOMAIN
    ]

    assert len(sensor_entities) == 4

    entity_unique_ids = {entity.unique_id for entity in sensor_entities}
    assert "ff:ff:ff:ff:ff:ff_expires" in entity_unique_ids
    assert "ff:ff:ff:ff:ff:ff_interface" in entity_unique_ids
    assert "ff:ff:ff:ff:ff:fe_expires" in entity_unique_ids
    assert "ff:ff:ff:ff:ff:fe_interface" in entity_unique_ids


@pytest.mark.usefixtures("mock_opnsense_client")
async def test_sensor_states(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test OPNsense sensor states."""
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    sensor_entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    sensor_entities = [
        entity for entity in sensor_entities if entity.domain == sensor.DOMAIN
    ]
    entity_ids_by_unique_id = {
        entity.unique_id: entity.entity_id for entity in sensor_entities
    }

    expires_entry = next(
        entity
        for entity in sensor_entities
        if entity.unique_id == "ff:ff:ff:ff:ff:fe_expires"
    )
    assert expires_entry.disabled_by is RegistryEntryDisabler.INTEGRATION
    assert hass.states.get(expires_entry.entity_id) is None

    interface_state = hass.states.get(
        entity_ids_by_unique_id["ff:ff:ff:ff:ff:fe_interface"]
    )
    assert interface_state is not None
    assert interface_state.state == "LAN"


@pytest.mark.usefixtures("mock_opnsense_client")
async def test_sensor_device_info_defaults(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test OPNsense sensor device defaults in the device registry."""
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    unnamed_device = device_registry.async_get_device(
        connections={(CONNECTION_NETWORK_MAC, "ff:ff:ff:ff:ff:ff")}
    )
    assert unnamed_device is not None
    assert unnamed_device.name is None
    assert unnamed_device.manufacturer is None

    named_device = device_registry.async_get_device(
        connections={(CONNECTION_NETWORK_MAC, "ff:ff:ff:ff:ff:fe")}
    )
    assert named_device is not None
    assert named_device.name == "Desktop"
    assert named_device.manufacturer == "OEM"
