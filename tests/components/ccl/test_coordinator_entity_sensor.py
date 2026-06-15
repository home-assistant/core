"""Tests for CCL coordinator, entity and sensor behavior."""

from __future__ import annotations

import time
from unittest.mock import MagicMock

from aioccl import CCLSensorTypes
import pytest

from homeassistant.components.ccl import sensor as ccl_sensor
from homeassistant.components.ccl.coordinator import CCLCoordinator
from homeassistant.components.ccl.entity import CCLEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import MockConfigEntry


async def test_coordinator_returns_empty_when_no_last_update(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that coordinator returns empty dict when no last update time is set."""
    device = MagicMock()
    device.device_id = "dev1"

    coordinator = CCLCoordinator(hass, device, mock_config_entry)

    # When last_update_time is None the coordinator should return an empty dict
    assert await coordinator._async_update_data() == {}


async def test_coordinator_raises_when_timed_out(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that coordinator raises UpdateFailed when device times out."""
    device = MagicMock()
    device.device_id = "dev1"

    coordinator = CCLCoordinator(hass, device, mock_config_entry)

    # Simulate a last update in the past beyond the checking interval
    coordinator.last_update_time = time.monotonic() - (601)

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


async def test_coordinator_raises_on_device_exception(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_ccl: MagicMock
) -> None:
    """Test that coordinator raises UpdateFailed when device raises exception."""
    # mock_ccl.get_sensors is configured in the conftest to raise CCLDataUpdateException
    coordinator = CCLCoordinator(hass, mock_ccl, mock_config_entry)
    coordinator.last_update_time = time.monotonic()

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


async def test_coordinator_returns_sensors_when_available(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that coordinator returns sensor data when available from device."""
    device = MagicMock()
    device.device_id = "dev1"
    sensor_obj = MagicMock()
    device.get_sensors.return_value = {"k": sensor_obj}

    coordinator = CCLCoordinator(hass, device, mock_config_entry)
    coordinator.last_update_time = time.monotonic()

    assert await coordinator._async_update_data() == {"k": sensor_obj}


def _make_internal_sensor(
    key: str,
    name: str,
    sensor_type,
    compartment: str | None = None,
    value: object | None = None,
):
    """Create a mock internal sensor object for testing."""
    obj = MagicMock()
    obj.key = key
    obj.name = name
    obj.sensor_type = sensor_type
    obj.compartment = compartment
    obj.value = value
    return obj


def test_ccl_entity_device_id_and_name_with_and_without_compartment(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test CCLEntity device ID and name generation with and without compartment."""
    # Create a fake device and coordinator-like object
    device = MagicMock()
    device.device_id = "DevID"
    device.name = "DevName"
    device.model = "MODEL"
    device.fw_ver = "v1"

    coordinator = MagicMock()
    coordinator.device = device

    # Internal sensor without compartment
    internal = _make_internal_sensor("k1", "Sensor 1", None, compartment=None)
    entity = CCLEntity(internal, coordinator)
    assert entity.device_id == "DevID"
    assert entity.device_name == "DevName"
    assert entity._attr_unique_id == "DevID-k1"
    assert entity._attr_device_info["model"] == device.model

    # Internal sensor with compartment
    internal2 = _make_internal_sensor("k2", "Sensor 2", None, compartment="Top")
    entity2 = CCLEntity(internal2, coordinator)
    assert entity2.device_id == "devid_top"
    assert "Top" in entity2.device_name


async def test_async_setup_entry_adds_entities_and_native_value(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that async_setup_entry creates sensor entities with correct values."""
    # Prepare a device and coordinator
    device = MagicMock()
    device.device_id = "devx"
    device.name = "Device X"
    device.model = "M"
    device.fw_ver = "1.2.3"

    # Create two sensors: one with translation_key None (TEMPERATURE) and one with translation_key set (UVI)
    temp = _make_internal_sensor(
        "t", "Temp Sensor", CCLSensorTypes.TEMPERATURE, compartment=None, value=21
    )
    uvi = _make_internal_sensor(
        "u", "UVI Sensor", CCLSensorTypes.UVI, compartment=None, value=5
    )

    coordinator = MagicMock()
    coordinator.device = device
    coordinator.data = {"t": temp, "u": uvi}

    # Attach coordinator to a config entry (async_setup_entry expects entry.runtime_data)
    mock_config_entry.runtime_data = coordinator

    added: list = []

    def async_add_entities(entities):
        added.extend(entities)

    await ccl_sensor.async_setup_entry(hass, mock_config_entry, async_add_entities)

    # Two entities should have been added
    assert len(added) == 2

    # Find the temperature and uvi entities
    temp_entity = next(e for e in added if e.entity_description.key == "t")
    uvi_entity = next(e for e in added if e.entity_description.key == "u")

    # Temperature description should have been replaced to include name
    assert temp_entity.entity_description.name == "Temp Sensor"

    # UVI uses translation_key, so translation_key should be present and name not set
    assert uvi_entity.entity_description.translation_key == "uvi"
    assert uvi_entity.native_value == 5
