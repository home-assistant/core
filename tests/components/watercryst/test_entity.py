"""Tests for WATERCryst entities."""

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.components.watercryst.const import DOMAIN
from homeassistant.components.watercryst.entity import (
    WatercrystMeasurementsEntity,
    WatercrystStateEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.entity import Entity

from .conftest import (
    BIOCAT_SERIAL,
    CONFIG_ENTRY_ID,
    DEVICE_MANUFACTURER,
    DEVICE_NAME,
    DEVICE_TYPE_LINE,
    DEVICE_TYPE_NUMBER,
    DEVICE_TYPE_SERIES,
    FW_VERSION,
    HW_VERSION,
    SYSTEM_MAC_NORMALIZED,
)


@pytest.mark.parametrize(
    "EntityType",
    [WatercrystStateEntity, WatercrystMeasurementsEntity],
)
async def test_state_entity_initialization(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, EntityType: type[Entity]
) -> None:
    """Test WATERCryst state entity attributes."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    description = SensorEntityDescription(key="pressure")

    entity = EntityType(
        config_entry=mock_config_entry,
        coordinator=mock_config_entry.runtime_data,
        entity_description=description,
    )

    assert entity.unique_id == f"{CONFIG_ENTRY_ID}_pressure"
    assert entity.entity_description is description
    assert entity.device_info.identifiers == {(DOMAIN, CONFIG_ENTRY_ID)}
    assert entity.device_info.connections == {
        (CONNECTION_NETWORK_MAC, SYSTEM_MAC_NORMALIZED)
    }
    assert entity.device_info.manufacturer == DEVICE_MANUFACTURER
    assert entity.device_info.model == f"{DEVICE_TYPE_LINE} {DEVICE_TYPE_SERIES}"
    assert entity.device_info.model_id == DEVICE_TYPE_NUMBER
    assert entity.device_info.name == DEVICE_NAME
    assert entity.device_info.serial_number == BIOCAT_SERIAL
    assert entity.device_info.sw_version == FW_VERSION
    assert entity.device_info.hw_version == HW_VERSION
    assert (
        entity.device_info.configuration_url
        == f"https://app.watercryst.com/devices/{BIOCAT_SERIAL}"
    )
    assert entity.should_poll is False
    assert entity.has_entity_name is True


@pytest.mark.parametrize(
    "EntityType",
    [WatercrystStateEntity, WatercrystMeasurementsEntity],
)
async def test_state_entity_initialization_missing(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, EntityType: type[Entity]
) -> None:
    """Test WATERCryst state entity attributes."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_config_entry.runtime_data.data.name = None
    mock_config_entry.runtime_data.data.system_mac_address = None

    description = SensorEntityDescription(key="pressure")

    entity = EntityType(
        config_entry=mock_config_entry,
        coordinator=mock_config_entry.runtime_data,
        entity_description=description,
    )

    assert entity.unique_id == f"{CONFIG_ENTRY_ID}_pressure"
    assert entity.entity_description is description
    assert entity.device_info.identifiers == {(DOMAIN, CONFIG_ENTRY_ID)}
    assert entity.device_info.connections == set()
    assert entity.device_info.manufacturer == DEVICE_MANUFACTURER
    assert entity.device_info.model == f"{DEVICE_TYPE_LINE} {DEVICE_TYPE_SERIES}"
    assert entity.device_info.model_id == DEVICE_TYPE_NUMBER
    assert entity.device_info.name == BIOCAT_SERIAL
    assert entity.device_info.serial_number == BIOCAT_SERIAL
    assert entity.device_info.sw_version == FW_VERSION
    assert entity.device_info.hw_version == HW_VERSION
    assert (
        entity.device_info.configuration_url
        == f"https://app.watercryst.com/devices/{BIOCAT_SERIAL}"
    )
    assert entity.should_poll is False
    assert entity.has_entity_name is True
