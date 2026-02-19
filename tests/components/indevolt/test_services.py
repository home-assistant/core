"""Tests for Indevolt services/actions."""

from unittest.mock import AsyncMock, call

import pytest

from homeassistant.components.indevolt.const import (
    DOMAIN,
    ENERGY_MODE_WRITE_KEY,
    RT_MODE_KEY,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from . import setup_integration

from tests.common import MockConfigEntry

TARGET_ENTITY = "switch.cms_sf2000_allow_grid_charging"


@pytest.mark.parametrize("generation", [2], indirect=True)
async def test_service_change_mode(
    hass: HomeAssistant,
    mock_indevolt: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test change_mode service."""
    await setup_integration(hass, mock_config_entry)

    # Reset mock call count for this iteration
    mock_indevolt.set_data.reset_mock()

    # Call the service to change mode
    await hass.services.async_call(
        DOMAIN,
        "change_mode",
        {
            "entity_id": TARGET_ENTITY,
            "mode": "real_time_control",
        },
        blocking=True,
    )

    # Verify set_data was called with correct parameters
    mock_indevolt.set_data.assert_called_with(ENERGY_MODE_WRITE_KEY, 4)


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
            "entity_id": TARGET_ENTITY,
            "power": 1200,
            "target_soc": 60,
        },
        blocking=True,
    )

    # Verify set_data was called with correct parameters
    mock_indevolt.set_data.assert_has_calls(
        [call(ENERGY_MODE_WRITE_KEY, 4), call(RT_MODE_KEY, [1, 1200, 60])]
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
            "entity_id": TARGET_ENTITY,
            "power": 1200,
            "target_soc": 40,
        },
        blocking=True,
    )

    # Verify set_data was called with correct parameters
    mock_indevolt.set_data.assert_has_calls(
        [call(ENERGY_MODE_WRITE_KEY, 4), call(RT_MODE_KEY, [2, 1200, 40])]
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
        {"entity_id": TARGET_ENTITY},
        blocking=True,
    )

    # Verify set_data was called with correct parameters
    mock_indevolt.set_data.assert_has_calls(
        [call(ENERGY_MODE_WRITE_KEY, 4), call(RT_MODE_KEY, [0, 0, 0])]
    )


@pytest.mark.parametrize("generation", [2], indirect=True)
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
                "entity_id": TARGET_ENTITY,
                "power": 2500,
                "target_soc": 60,
            },
            blocking=True,
        )

    # Check for presence of expected error message
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
                "entity_id": TARGET_ENTITY,
                "power": 1000,
                "target_soc": 1,
            },
            blocking=True,
        )

    # Check for presence of expected error message
    assert "below emergency SOC" in str(exc_info.value)


@pytest.mark.parametrize("generation", [2], indirect=True)
async def test_service_missing_target(
    hass: HomeAssistant,
    mock_indevolt: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test services fail when target does not resolve to an indevolt entry."""
    await setup_integration(hass, mock_config_entry)

    # Mock call with invalid target
    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            "stop",
            {"entity_id": "switch.does_not_exist"},
            blocking=True,
        )

    # Check for presence of expected error message
    assert "No matching Indevolt" in str(exc_info.value)
