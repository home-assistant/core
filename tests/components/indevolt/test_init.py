"""Tests for the Indevolt integration initialization and services."""

import pytest

from homeassistant.components.indevolt import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr

from .conftest import setup_integration

from tests.common import MockConfigEntry


@pytest.mark.parametrize("generation", [2], indirect=True)
async def test_load_unload(
    hass: HomeAssistant, mock_indevolt, mock_config_entry: MockConfigEntry
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


@pytest.mark.parametrize("generation", [2], indirect=True)
async def test_load_failure(
    hass: HomeAssistant, mock_indevolt, mock_config_entry: MockConfigEntry
) -> None:
    """Test setup failure when coordinator update fails."""
    # Simulate timeout error during coordinator update
    mock_indevolt.fetch_data.side_effect = TimeoutError

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Verify the config entry enters retry state due to failure
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize("generation", [2], indirect=True)
async def test_service_charge(
    hass: HomeAssistant,
    mock_indevolt,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the charge service."""
    await setup_integration(hass, mock_config_entry)

    # Get device ID
    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, mock_config_entry.entry_id)}
    )
    assert device_entry

    # Call charge service
    await hass.services.async_call(
        DOMAIN,
        "charge",
        {"device_id": device_entry.id, "power": 1500},
        blocking=True,
    )

    # Verify API calls - mode switch to 4, then charge command
    assert mock_indevolt.set_data.call_count == 2
    mock_indevolt.set_data.assert_any_call("47005", 4)
    mock_indevolt.set_data.assert_any_call("47015", [1, 1500, 92])


@pytest.mark.parametrize("generation", [1], indirect=True)
async def test_service_charge_exceeds_power_limit(
    hass: HomeAssistant,
    mock_indevolt,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the charge service with power exceeding limit."""
    await setup_integration(hass, mock_config_entry)

    # Get device ID
    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, mock_config_entry.entry_id)}
    )
    assert device_entry

    # Call charge service with power exceeding Gen1 limit (1200W)
    with pytest.raises(ServiceValidationError, match="exceeds maximum 1200W"):
        await hass.services.async_call(
            DOMAIN,
            "charge",
            {"device_id": device_entry.id, "power": 1500},
            blocking=True,
        )


@pytest.mark.parametrize("generation", [2], indirect=True)
async def test_service_discharge(
    hass: HomeAssistant,
    mock_indevolt,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the discharge service."""
    await setup_integration(hass, mock_config_entry)

    # Get device ID
    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, mock_config_entry.entry_id)}
    )
    assert device_entry

    # Call discharge service
    await hass.services.async_call(
        DOMAIN,
        "discharge",
        {"device_id": device_entry.id, "power": 2000},
        blocking=True,
    )

    # Verify API calls - mode switch to 4, then discharge command
    assert mock_indevolt.set_data.call_count == 2
    mock_indevolt.set_data.assert_any_call("47005", 4)
    mock_indevolt.set_data.assert_any_call("47015", [2, 2000, 5])


@pytest.mark.parametrize("generation", [2], indirect=True)
async def test_service_stop(
    hass: HomeAssistant,
    mock_indevolt,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the stop service."""
    await setup_integration(hass, mock_config_entry)

    # Get device ID
    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, mock_config_entry.entry_id)}
    )
    assert device_entry

    # Call stop service
    await hass.services.async_call(
        DOMAIN,
        "stop",
        {"device_id": device_entry.id},
        blocking=True,
    )

    # Verify API calls - mode switch to 4, then stop command
    assert mock_indevolt.set_data.call_count == 2
    mock_indevolt.set_data.assert_any_call("47005", 4)
    mock_indevolt.set_data.assert_any_call("47015", [0, 0, 0])


@pytest.mark.parametrize("generation", [2], indirect=True)
async def test_service_change_mode(
    hass: HomeAssistant,
    mock_indevolt,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the change_mode service."""
    await setup_integration(hass, mock_config_entry)

    # Get device ID
    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, mock_config_entry.entry_id)}
    )
    assert device_entry

    # Call change_mode service to switch to real_time_control (mode 4)
    await hass.services.async_call(
        DOMAIN,
        "change_mode",
        {"device_id": device_entry.id, "mode": "real_time_control"},
        blocking=True,
    )

    # Verify API call - mode switch from 1 to 4
    mock_indevolt.set_data.assert_called_once_with("47005", 4)
