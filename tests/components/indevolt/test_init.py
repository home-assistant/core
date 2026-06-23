"""Tests for the Indevolt integration initialization and services."""

from unittest.mock import AsyncMock

import pytest

from homeassistant.components.indevolt.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC

from . import setup_integration
from .conftest import DEVICE_MAPPING, TEST_DEVICE_SN_GEN2

from tests.common import MockConfigEntry


@pytest.mark.parametrize("generation", [2], indirect=True)
async def test_load_unload(
    hass: HomeAssistant, mock_indevolt: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test setting up and removing a config entry."""
    await setup_integration(hass, mock_config_entry)

    # Verify the config entry is successfully loaded
    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Unload the integration
    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Verify the config entry is properly unloaded
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize("generation", [1, 2], indirect=True)
async def test_device_info(
    hass: HomeAssistant,
    mock_indevolt: AsyncMock,
    mock_config_entry: MockConfigEntry,
    generation: int,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test that device info is correctly registered in the device registry."""
    await setup_integration(hass, mock_config_entry)

    device_info = DEVICE_MAPPING[generation]
    device_entry = device_registry.async_get_device(
        connections={(CONNECTION_NETWORK_MAC, device_info["mac"])}
    )

    assert device_entry is not None
    assert device_entry.manufacturer == "INDEVOLT"
    assert device_entry.model == device_info["device"]
    assert device_entry.serial_number == device_info["sn"]
    assert device_entry.sw_version == device_info["fw"]
    assert device_entry.hw_version == str(device_info["generation"])
    assert (CONNECTION_NETWORK_MAC, device_info["mac"]) in device_entry.connections


@pytest.mark.parametrize("generation", [2], indirect=True)
async def test_load_failure(
    hass: HomeAssistant, mock_indevolt: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test setup failure when coordinator update fails."""
    # Simulate timeout error during coordinator initialization
    mock_indevolt.get_config.side_effect = TimeoutError

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Verify the config entry enters retry state due to failure
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize("generation", [2], indirect=True)
async def test_migrate_main_heating_state_unique_id(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_indevolt: AsyncMock,
    mock_config_entry_v1_1: MockConfigEntry,
) -> None:
    """Test migration of MAIN_HEATING_STATE unique ID from 9079 to 9080."""
    mock_config_entry_v1_1.add_to_hass(hass)

    old_unique_id = f"{TEST_DEVICE_SN_GEN2}_9079"
    new_unique_id = f"{TEST_DEVICE_SN_GEN2}_9080"

    entity_registry.async_get_or_create(
        "binary_sensor",
        DOMAIN,
        old_unique_id,
        config_entry=mock_config_entry_v1_1,
    )

    assert mock_config_entry_v1_1.minor_version == 1

    await hass.config_entries.async_setup(mock_config_entry_v1_1.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry_v1_1.minor_version == 2
    assert entity_registry.async_get_entity_id("binary_sensor", DOMAIN, new_unique_id)
    assert not entity_registry.async_get_entity_id(
        "binary_sensor", DOMAIN, old_unique_id
    )
