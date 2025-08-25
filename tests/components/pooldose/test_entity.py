"""Test the PoolDose entity module."""

import json
from unittest.mock import patch

import pytest

from homeassistant.components.pooldose.const import DOMAIN, MANUFACTURER
from homeassistant.components.pooldose.entity import PooldoseEntity, device_info
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.entity import EntityDescription

from tests.common import MockConfigEntry, async_load_fixture


@pytest.mark.usefixtures("mock_pooldose_client")
async def test_device_info_complete_data(hass: HomeAssistant) -> None:
    """Test device_info function with complete device data."""
    device_data_raw = await async_load_fixture(hass, "deviceinfo.json", DOMAIN)
    device_data = json.loads(device_data_raw)
    unique_id = "TEST123456789"

    info = device_info(device_data, unique_id)

    assert info["identifiers"] == {(DOMAIN, unique_id)}
    assert info["manufacturer"] == MANUFACTURER
    assert info["model"] == "POOL DOSE"
    assert info["model_id"] == "PDPR1H1HAW100"
    assert info["name"] == "Pool Device"
    assert info["serial_number"] == unique_id
    assert info["sw_version"] == "1.30 (SW v2.10, API v1)"
    assert info["hw_version"] == "539187"
    assert info["connections"] == {(CONNECTION_NETWORK_MAC, "AA:BB:CC:DD:EE:FF")}
    assert info["configuration_url"] == "http://192.168.1.100/index.html"


async def test_device_info_minimal_data() -> None:
    """Test device_info function with minimal device data."""
    device_data = {"NAME": "Test Device"}
    unique_id = "TEST123"

    info = device_info(device_data, unique_id)

    assert info["identifiers"] == {(DOMAIN, unique_id)}
    assert info["manufacturer"] == MANUFACTURER
    assert info["name"] == "Test Device"
    assert info["serial_number"] == unique_id
    # All other fields should be None
    assert info["model"] is None
    assert info["model_id"] is None
    assert info["sw_version"] is None
    assert info["hw_version"] is None
    assert info["connections"] == set()
    assert info["configuration_url"] is None


async def test_device_info_none_data() -> None:
    """Test device_info function with None device data."""
    unique_id = "TEST123"

    info = device_info(None, unique_id)

    assert info["identifiers"] == {(DOMAIN, unique_id)}
    assert info["manufacturer"] == MANUFACTURER
    assert info["serial_number"] == unique_id
    # All other fields should be None
    assert info["name"] is None
    assert info["model"] is None
    assert info["model_id"] is None
    assert info["sw_version"] is None
    assert info["hw_version"] is None
    assert info["connections"] == set()
    assert info["configuration_url"] is None


async def test_device_info_partial_sw_version() -> None:
    """Test device_info sw_version with partial data."""
    # Test with only FW_VERSION
    device_data = {"FW_VERSION": "1.30"}
    info = device_info(device_data, "TEST123")
    assert info["sw_version"] is None

    # Test with FW_VERSION and SW_VERSION but no API_VERSION
    device_data = {"FW_VERSION": "1.30", "SW_VERSION": "2.10"}
    info = device_info(device_data, "TEST123")
    assert info["sw_version"] is None

    # Test with all required fields
    device_data = {
        "FW_VERSION": "1.30",
        "SW_VERSION": "2.10",
        "API_VERSION": "v1/",
    }
    info = device_info(device_data, "TEST123")
    assert info["sw_version"] == "1.30 (SW v2.10, API v1)"


async def test_device_info_api_version_strip_slash() -> None:
    """Test device_info strips trailing slash from API_VERSION."""
    device_data = {
        "FW_VERSION": "1.30",
        "SW_VERSION": "2.10",
        "API_VERSION": "v2.0/",  # With trailing slash
    }
    info = device_info(device_data, "TEST123")
    assert info["sw_version"] == "1.30 (SW v2.10, API v2.0)"


async def test_device_info_no_mac_address() -> None:
    """Test device_info without MAC address."""
    device_data = {"NAME": "Test Device"}
    info = device_info(device_data, "TEST123")
    assert info["connections"] == set()


async def test_device_info_no_ip_address() -> None:
    """Test device_info without IP address."""
    device_data = {"NAME": "Test Device"}
    info = device_info(device_data, "TEST123")
    assert info["configuration_url"] is None


@pytest.mark.usefixtures("mock_pooldose_client")
async def test_pooldose_entity_initialization(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test PoolDose entity initialization."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state == ConfigEntryState.LOADED

    # Get coordinator and device properties
    runtime_data = mock_config_entry.runtime_data
    coordinator = runtime_data.coordinator
    device_properties = runtime_data.device_properties
    serial_number = mock_config_entry.unique_id

    # Create test entity description
    entity_description = EntityDescription(key="test_sensor")

    # Create entity instance
    entity = PooldoseEntity(
        coordinator,
        serial_number,
        device_properties,
        entity_description,
        "sensor",
    )

    # Test entity properties
    assert entity._attr_has_entity_name is True
    assert entity._attr_unique_id == f"{serial_number}_test_sensor"
    assert entity.entity_description == entity_description
    assert entity.platform_name == "sensor"

    # Test device_info is set correctly
    assert entity._attr_device_info["identifiers"] == {(DOMAIN, serial_number)}
    assert entity._attr_device_info["name"] == "Pool Device"


@pytest.mark.usefixtures("mock_pooldose_client")
async def test_pooldose_entity_available_property(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test PoolDose entity available property logic."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    runtime_data = mock_config_entry.runtime_data
    coordinator = runtime_data.coordinator
    device_properties = runtime_data.device_properties
    serial_number = mock_config_entry.unique_id

    entity_description = EntityDescription(key="temperature")
    entity = PooldoseEntity(
        coordinator,
        serial_number,
        device_properties,
        entity_description,
        "sensor",
    )

    # Test available when coordinator has data and entity key exists
    assert entity.available is True

    # Test unavailable when coordinator data is None
    coordinator.data = None
    assert entity.available is False

    # Test unavailable when platform data is missing
    coordinator.data = {"other_platform": {}}
    assert entity.available is False

    # Test unavailable when entity key is missing
    coordinator.data = {"sensor": {"other_sensor": {}}}
    assert entity.available is False

    # Test available when entity key exists
    coordinator.data = {"sensor": {"temperature": {"value": 25}}}
    assert entity.available is True


@pytest.mark.usefixtures("mock_pooldose_client")
async def test_pooldose_entity_get_data_method(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test PoolDose entity get_data method."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    runtime_data = mock_config_entry.runtime_data
    coordinator = runtime_data.coordinator
    device_properties = runtime_data.device_properties
    serial_number = mock_config_entry.unique_id

    entity_description = EntityDescription(key="temperature")
    entity = PooldoseEntity(
        coordinator,
        serial_number,
        device_properties,
        entity_description,
        "sensor",
    )

    # Test get_data returns correct data when available
    expected_data = {"value": 25, "unit": "°C"}
    coordinator.data = {"sensor": {"temperature": expected_data}}
    assert entity.get_data() == expected_data

    # Test get_data returns None when entity is unavailable
    coordinator.data = None
    assert entity.get_data() is None

    # Test get_data returns None when platform data is missing
    coordinator.data = {"other_platform": {}}
    assert entity.get_data() is None

    # Test get_data returns None when entity key is missing
    coordinator.data = {"sensor": {"other_sensor": {}}}
    assert entity.get_data() is None


@pytest.mark.usefixtures("mock_pooldose_client")
async def test_pooldose_entity_coordinator_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test PoolDose entity when coordinator itself is unavailable."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    runtime_data = mock_config_entry.runtime_data
    coordinator = runtime_data.coordinator
    device_properties = runtime_data.device_properties
    serial_number = mock_config_entry.unique_id

    entity_description = EntityDescription(key="temperature")
    entity = PooldoseEntity(
        coordinator,
        serial_number,
        device_properties,
        entity_description,
        "sensor",
    )

    # Mock coordinator.last_update_success to make it unavailable
    with patch.object(coordinator, "last_update_success", False):
        assert entity.available is False
        assert entity.get_data() is None
