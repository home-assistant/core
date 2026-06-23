"""Tests for the OPNsense sensor platform."""

from datetime import timedelta
from unittest.mock import AsyncMock

import pytest

from homeassistant.components import sensor
from homeassistant.components.opnsense.sensor import (
    SENSOR_DESCRIPTIONS,
    OPNsenseSensorEntity,
)
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.entity_registry import RegistryEntryDisabler
from homeassistant.util import dt as dt_util

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


@pytest.mark.usefixtures("mock_opnsense_client")
async def test_expires_sensor_with_non_int_value_is_unknown(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test timestamp sensor returns unknown when source value is not an int."""
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    sensor_entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    expires_entity = next(
        entity
        for entity in sensor_entities
        if entity.unique_id == "ff:ff:ff:ff:ff:fe_expires"
    )

    entity_registry.async_update_entity(expires_entity.entity_id, disabled_by=None)
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(expires_entity.entity_id)
    assert state is not None
    assert state.state == "unknown"


async def test_interface_sensor_casts_non_string_values(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opnsense_client: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test non-string values are converted to string for non-timestamp sensors."""
    arp_devices = [
        {
            "expires": "2026-06-01T10:00:00+00:00",
            "hostname": "",
            "intf": "igb1",
            "intf_description": 12,
            "ip": "192.168.0.123",
            "mac": "ff:ff:ff:ff:ff:ff",
            "manufacturer": "",
        }
    ]
    mock_opnsense_client.get_arp_table.return_value = arp_devices

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    sensor_entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    interface_entity = next(
        entity
        for entity in sensor_entities
        if entity.unique_id == "ff:ff:ff:ff:ff:ff_interface"
    )

    state = hass.states.get(interface_entity.entity_id)
    assert state is not None
    assert state.state == "12"


@pytest.mark.usefixtures("mock_opnsense_client")
async def test_native_value_is_none_when_sensor_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test native_value is None when the tracked device is unavailable."""
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    description = next(
        sensor_description
        for sensor_description in SENSOR_DESCRIPTIONS
        if sensor_description.device_class is SensorDeviceClass.TIMESTAMP
    )
    coordinator = mock_config_entry.runtime_data.coordinator
    entity = OPNsenseSensorEntity(coordinator, "00:00:00:00:00:00", description)

    assert entity.available is False
    assert entity.native_value is None


@pytest.mark.usefixtures("mock_opnsense_client")
@pytest.mark.freeze_time("2026-06-01T10:00:00+00:00")
async def test_expires_sensor_returns_timestamp_for_int_value(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opnsense_client: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test timestamp sensor converts integer seconds to a timestamp."""
    arp_devices = [
        {
            "expires": 120,
            "hostname": "Desktop",
            "intf": "igb1",
            "intf_description": "LAN",
            "ip": "192.168.0.167",
            "mac": "ff:ff:ff:ff:ff:fe",
            "manufacturer": "OEM",
        }
    ]
    mock_opnsense_client.get_arp_table.return_value = arp_devices

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    sensor_entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    expires_entity = next(
        entity
        for entity in sensor_entities
        if entity.unique_id == "ff:ff:ff:ff:ff:fe_expires"
    )

    entity_registry.async_update_entity(expires_entity.entity_id, disabled_by=None)
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(expires_entity.entity_id)
    assert state is not None
    assert state.state != "unknown"
    assert dt_util.parse_datetime(state.state) == dt_util.utcnow() + timedelta(
        seconds=120
    )
