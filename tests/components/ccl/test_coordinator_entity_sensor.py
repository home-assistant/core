"""Tests for CCL coordinator, entity and sensor behavior."""

from __future__ import annotations

import time
from unittest.mock import MagicMock

from aioccl import CCLSensorTypes
import pytest

from homeassistant.components.ccl.const import DOMAIN
from homeassistant.components.ccl.coordinator import CCLCoordinator
from homeassistant.components.ccl.entity import CCLEntity
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_WEBHOOK_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import EntityRegistry
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
    hass: HomeAssistant,
) -> None:
    """Test that async_setup_entry creates sensor entities with correct values."""
    # Create two sensors: one with translation_key None (TEMPERATURE) and one with translation_key set (UVI)
    temp = _make_internal_sensor(
        "t", "Temp Sensor", CCLSensorTypes.TEMPERATURE, compartment=None, value=21
    )
    uvi = _make_internal_sensor(
        "u", "UVI Sensor", CCLSensorTypes.UVI, compartment=None, value=5
    )

    # Mock device
    device = MagicMock()
    device.device_id = "devx"
    device.name = "Device X"
    device.model = "M"
    device.fw_ver = "1.2.3"
    device.get_sensors.return_value = {"t": temp, "u": uvi}

    # Store the callback so we can trigger it
    def store_callback(callback):
        # Trigger the callback with initial data
        callback({"t": temp, "u": uvi})

    device.set_update_callback = store_callback

    # Create config entry with the mock device
    config_entry = MockConfigEntry(
        title="CCL Weather Station",
        domain=DOMAIN,
        data={
            CONF_WEBHOOK_ID: "c2507426",
            CONF_HOST: "192.168.1.185",
            CONF_PORT: "8123",
            "device": device,
        },
        unique_id="0000-0000",
    )

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Get the entity registry
    entity_registry: EntityRegistry = hass.data["entity_registry"]

    # Find the temperature and UVI entities in the registry
    entities = [
        entity
        for entity in entity_registry.entities.values()
        if entity.domain == "sensor"
    ]
    assert len(entities) == 2

    # Verify the entities have the expected sensor types
    entity_keys = {entity.unique_id for entity in entities}
    assert "devx-t" in entity_keys
    assert "devx-u" in entity_keys
