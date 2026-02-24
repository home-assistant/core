"""Tests for Indevolt services/actions."""

from unittest.mock import AsyncMock, call

import pytest

from homeassistant.components.indevolt.const import (
    DOMAIN,
    ENERGY_MODE_READ_KEY,
    ENERGY_MODE_WRITE_KEY,
    PORTABLE_MODE,
    REALTIME_ACTION_KEY,
    REALTIME_ACTION_MODE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr

from . import setup_integration

from tests.common import MockConfigEntry


def _get_device_id(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> str:
    """Return the device registry ID for the given config entry."""
    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, mock_config_entry.unique_id)}
    )
    assert device_entry is not None
    return device_entry.id


@pytest.mark.parametrize("generation", [2], indirect=True)
async def test_service_charge(
    hass: HomeAssistant,
    mock_indevolt: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test charge service."""
    await setup_integration(hass, mock_config_entry)

    # Reset mock call count for this iteration
    mock_indevolt.set_data.reset_mock()

    # Call the service to start charging
    await hass.services.async_call(
        DOMAIN,
        "charge",
        {
            "device_ids": [_get_device_id(hass, mock_config_entry)],
            "power": 1200,
            "target_soc": 60,
        },
        blocking=True,
    )

    # Verify set_data was called with correct parameters
    mock_indevolt.set_data.assert_has_calls(
        [
            call(ENERGY_MODE_WRITE_KEY, REALTIME_ACTION_MODE),
            call(REALTIME_ACTION_KEY, [1, 1200, 60]),
        ]
    )


@pytest.mark.parametrize("generation", [2], indirect=True)
async def test_service_discharge(
    hass: HomeAssistant,
    mock_indevolt: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test discharge service."""
    await setup_integration(hass, mock_config_entry)

    # Reset mock call count for this iteration
    mock_indevolt.set_data.reset_mock()

    # Call the service to start discharging
    await hass.services.async_call(
        DOMAIN,
        "discharge",
        {
            "device_ids": [_get_device_id(hass, mock_config_entry)],
            "power": 1200,
            "target_soc": 40,
        },
        blocking=True,
    )

    # Verify set_data was called with correct parameters
    mock_indevolt.set_data.assert_has_calls(
        [
            call(ENERGY_MODE_WRITE_KEY, REALTIME_ACTION_MODE),
            call(REALTIME_ACTION_KEY, [2, 1200, 40]),
        ]
    )


@pytest.mark.parametrize("generation", [2], indirect=True)
async def test_service_stop(
    hass: HomeAssistant,
    mock_indevolt: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test stop service."""
    await setup_integration(hass, mock_config_entry)

    # Reset mock call count for this iteration
    mock_indevolt.set_data.reset_mock()

    # Call the service to stop the battery
    await hass.services.async_call(
        DOMAIN,
        "stop",
        {"device_ids": [_get_device_id(hass, mock_config_entry)]},
        blocking=True,
    )

    # Verify set_data was called with correct parameters
    mock_indevolt.set_data.assert_has_calls(
        [
            call(ENERGY_MODE_WRITE_KEY, REALTIME_ACTION_MODE),
            call(REALTIME_ACTION_KEY, [0, 0, 0]),
        ]
    )


@pytest.mark.parametrize("generation", [1], indirect=True)
async def test_service_charge_power_too_high(
    hass: HomeAssistant,
    mock_indevolt: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test charge service validation for max power."""
    await setup_integration(hass, mock_config_entry)

    # Mock call with invalid power
    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            "charge",
            {
                "device_ids": [_get_device_id(hass, mock_config_entry)],
                "power": 1300,
                "target_soc": 60,
            },
            blocking=True,
        )

    # Verify error includes expected error string
    assert "exceeds maximum" in str(exc_info.value)


@pytest.mark.parametrize("generation", [2], indirect=True)
async def test_service_charge_target_soc_below_emergency(
    hass: HomeAssistant,
    mock_indevolt: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test charge service validation for target SOC."""
    await setup_integration(hass, mock_config_entry)

    # Mock call with invalid SOC
    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            "charge",
            {
                "device_ids": [_get_device_id(hass, mock_config_entry)],
                "power": 1000,
                "target_soc": 1,
            },
            blocking=True,
        )

    # Verify error includes expected error string
    assert "below emergency SOC" in str(exc_info.value)


@pytest.mark.parametrize("generation", [2], indirect=True)
async def test_service_missing_target(
    hass: HomeAssistant,
    mock_indevolt: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test services fail when target does not resolve to an indevolt entry."""
    await setup_integration(hass, mock_config_entry)

    # Mock call with an unknown device ID
    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            "stop",
            {"device_ids": ["non-existent-device-id"]},
            blocking=True,
        )

    # Verify error is raised with correct translation key
    assert exc_info.value.translation_key == "no_matching_target_entries"


@pytest.mark.parametrize("generation", [2], indirect=True)
async def test_charge_outdoor_portable(
    hass: HomeAssistant,
    mock_indevolt: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test charge service fails when device is in outdoor/portable mode."""
    await setup_integration(hass, mock_config_entry)

    # Force outdoor/portable mode
    coordinator = mock_config_entry.runtime_data
    coordinator.data[ENERGY_MODE_READ_KEY] = PORTABLE_MODE

    # Mock call with device in outdoor/portable mode
    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            "charge",
            {
                "device_ids": [_get_device_id(hass, mock_config_entry)],
                "power": 500,
                "target_soc": 100,
            },
            blocking=True,
        )

    # Verify error is raised with correct translation key
    assert (
        exc_info.value.translation_key
        == "energy_mode_change_unavailable_outdoor_portable"
    )
