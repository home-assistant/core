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

    # Mock call to start charging
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

    # Mock call to start discharging
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


@pytest.mark.parametrize("generation", [1], indirect=True)
async def test_service_charge_power_too_high(
    hass: HomeAssistant,
    mock_indevolt: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test charge service validation for max power."""
    await setup_integration(hass, mock_config_entry)

    # Mock call to start charging (exceed charge power for gen 1)
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

    # Verify correct translation key is used for the error
    assert exc_info.value.translation_key == "power_exceeds_max"


@pytest.mark.parametrize("generation", [2], indirect=True)
async def test_service_charge_target_soc_below_emergency(
    hass: HomeAssistant,
    mock_indevolt: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test charge service validation for target SOC."""
    await setup_integration(hass, mock_config_entry)

    # Mock call to start charging (target SOC < Emergency SOC)
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

    # Verify correct translation key is used for the error
    assert exc_info.value.translation_key == "soc_below_emergency"


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
            "discharge",
            {
                "device_ids": ["non-existent-device-id"],
                "power": 500,
                "target_soc": 50,
            },
            blocking=True,
        )

    # Verify correct translation key is used for the error
    assert exc_info.value.translation_key == "no_matching_target_entries"


@pytest.mark.parametrize("generation", [1], indirect=True)
async def test_service_discharge_power_too_high(
    hass: HomeAssistant,
    mock_indevolt: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test discharge service validation for max power."""
    await setup_integration(hass, mock_config_entry)

    # Mock call to start discharging (exceed discharge power for gen 1)
    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            "discharge",
            {
                "device_ids": [_get_device_id(hass, mock_config_entry)],
                "power": 1000,
                "target_soc": 20,
            },
            blocking=True,
        )

    # Verify correct translation key is used for the error
    assert exc_info.value.translation_key == "power_exceeds_max"


@pytest.mark.parametrize("generation", [2], indirect=True)
async def test_service_discharge_target_soc_below_emergency(
    hass: HomeAssistant,
    mock_indevolt: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test discharge service validation for target SOC."""
    await setup_integration(hass, mock_config_entry)

    # Mock call to start discharging (target SOC < Emergency SOC)
    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            "discharge",
            {
                "device_ids": [_get_device_id(hass, mock_config_entry)],
                "power": 1000,
                "target_soc": 1,
            },
            blocking=True,
        )

    # Verify correct translation key is used for the error
    assert exc_info.value.translation_key == "soc_below_emergency"


@pytest.mark.parametrize("generation", [2], indirect=True)
@pytest.mark.parametrize("alt_generation", [1], indirect=True)
async def test_multi_device_discharge_partial_validation_failure(
    hass: HomeAssistant,
    mock_indevolt: AsyncMock,
    mock_config_entry: MockConfigEntry,
    alt_mock_config_entry: MockConfigEntry,
) -> None:
    """Test discharge with two devices where one fails power validation."""

    # Set up multiple devices (gen 1 & gen 2)
    await setup_integration(hass, mock_config_entry)
    await setup_integration(hass, alt_mock_config_entry)

    # Mock call to start discharging both devices (exceed discharge power for gen 1)
    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            "discharge",
            {
                "device_ids": [
                    _get_device_id(hass, mock_config_entry),
                    _get_device_id(hass, alt_mock_config_entry),
                ],
                "power": 1000,
                "target_soc": 20,
            },
            blocking=True,
        )

    # Confirm error references correct device (gen 1 fails, gen 2 does not)
    assert exc_info.value.translation_key == "multi_device_errors"
    errors = exc_info.value.translation_placeholders["errors"]
    assert alt_mock_config_entry.title in errors
    assert mock_config_entry.title not in errors


@pytest.mark.parametrize("generation", [2], indirect=True)
@pytest.mark.parametrize("alt_generation", [1], indirect=True)
async def test_multi_device_discharge_full_validation_failure(
    hass: HomeAssistant,
    mock_indevolt: AsyncMock,
    mock_config_entry: MockConfigEntry,
    alt_mock_config_entry: MockConfigEntry,
) -> None:
    """Test discharge with two devices where both fail SOC validation."""

    # Set up multiple devices (gen 1 & gen 2)
    await setup_integration(hass, mock_config_entry)
    await setup_integration(hass, alt_mock_config_entry)

    # Mock call to start discharging both devices (target SOC < emergency SOC for both)
    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            "discharge",
            {
                "device_ids": [
                    _get_device_id(hass, mock_config_entry),
                    _get_device_id(hass, alt_mock_config_entry),
                ],
                "power": 100,
                "target_soc": 1,
            },
            blocking=True,
        )

    # Both device names should appear in the concatenated error message
    assert exc_info.value.translation_key == "multi_device_errors"
    errors = exc_info.value.translation_placeholders["errors"]
    assert mock_config_entry.title in errors
    assert alt_mock_config_entry.title in errors
    assert ";" in errors


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

    # Mock call to start charging (device in outdoor/portable mode)
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

    # Verify correct translation key is used for the error
    assert (
        exc_info.value.translation_key
        == "energy_mode_change_unavailable_outdoor_portable"
    )


@pytest.mark.parametrize("generation", [2], indirect=True)
async def test_service_charge_missing_energy_mode(
    hass: HomeAssistant,
    mock_indevolt: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test charge fails when current energy mode cannot be retrieved."""
    await setup_integration(hass, mock_config_entry)

    # Remove current energy mode value
    coordinator = mock_config_entry.runtime_data
    del coordinator.data[ENERGY_MODE_READ_KEY]

    # Mock call to start charging (current energy mode unknown)
    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            "charge",
            {
                "device_ids": [_get_device_id(hass, mock_config_entry)],
                "power": 500,
                "target_soc": 80,
            },
            blocking=True,
        )

    # Verify correct translation key is used for the error
    assert exc_info.value.translation_key == "failed_to_retrieve_current_energy_mode"


@pytest.mark.parametrize("generation", [2], indirect=True)
@pytest.mark.parametrize("alt_generation", [1], indirect=True)
async def test_multi_device_charge_partial_validation_failure(
    hass: HomeAssistant,
    mock_indevolt: AsyncMock,
    mock_config_entry: MockConfigEntry,
    alt_mock_config_entry: MockConfigEntry,
) -> None:
    """Test charge with two devices where one fails power validation."""

    # Set up multiple devices (gen 1 & gen 2)
    await setup_integration(hass, mock_config_entry)
    await setup_integration(hass, alt_mock_config_entry)

    # Mock call to start charging both devices (exceed discharge power for gen 1)
    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            "charge",
            {
                "device_ids": [
                    _get_device_id(hass, mock_config_entry),
                    _get_device_id(hass, alt_mock_config_entry),
                ],
                "power": 1300,
                "target_soc": 60,
            },
            blocking=True,
        )

    # Confirm error references correct device (gen 1 fails, gen 2 does not)
    assert exc_info.value.translation_key == "multi_device_errors"
    errors = exc_info.value.translation_placeholders["errors"]
    assert alt_mock_config_entry.title in errors
    assert mock_config_entry.title not in errors


@pytest.mark.parametrize("generation", [2], indirect=True)
@pytest.mark.parametrize("alt_generation", [1], indirect=True)
async def test_multi_device_charge_full_validation_failure(
    hass: HomeAssistant,
    mock_indevolt: AsyncMock,
    mock_config_entry: MockConfigEntry,
    alt_mock_config_entry: MockConfigEntry,
) -> None:
    """Test charge with two devices where both fail SOC validation."""

    # Set up multiple devices (gen 1 & gen 2)
    await setup_integration(hass, mock_config_entry)
    await setup_integration(hass, alt_mock_config_entry)

    # Mock call to start charging both devices (target SOC < emergency SOC for both)
    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            "charge",
            {
                "device_ids": [
                    _get_device_id(hass, mock_config_entry),
                    _get_device_id(hass, alt_mock_config_entry),
                ],
                "power": 100,
                "target_soc": 1,
            },
            blocking=True,
        )

    # Both device names should appear in the concatenated error message
    assert exc_info.value.translation_key == "multi_device_errors"
    errors = exc_info.value.translation_placeholders["errors"]
    assert mock_config_entry.title in errors
    assert alt_mock_config_entry.title in errors
    assert ";" in errors


@pytest.mark.parametrize("generation", [2], indirect=True)
async def test_single_device_execution_failure(
    hass: HomeAssistant,
    mock_indevolt: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that the original exception is re-raised for a single device execution failure."""
    await setup_integration(hass, mock_config_entry)

    # Simulate an API push failure
    mock_indevolt.set_data.side_effect = HomeAssistantError("Device push failed")

    # Mock call to start charging
    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            "charge",
            {
                "device_ids": [_get_device_id(hass, mock_config_entry)],
                "power": 500,
                "target_soc": 80,
            },
            blocking=True,
        )

    # Verify correct translation key is used for the error (for single coordinator)
    assert exc_info.value.translation_key != "service_call_failed"


@pytest.mark.parametrize("generation", [2], indirect=True)
@pytest.mark.parametrize("alt_generation", [1], indirect=True)
async def test_multi_device_execution_failure(
    hass: HomeAssistant,
    mock_indevolt: AsyncMock,
    mock_config_entry: MockConfigEntry,
    alt_mock_config_entry: MockConfigEntry,
) -> None:
    """Test that service_call_failed is raised when execution fails for multiple devices."""

    # Set up multiple devices (gen 1 & gen 2)
    await setup_integration(hass, mock_config_entry)
    await setup_integration(hass, alt_mock_config_entry)

    # Simulate an API push failure (triggers for both coordinators)
    mock_indevolt.set_data.side_effect = HomeAssistantError("Device push failed")

    # Mock call to start charging both devices
    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            "charge",
            {
                "device_ids": [
                    _get_device_id(hass, mock_config_entry),
                    _get_device_id(hass, alt_mock_config_entry),
                ],
                "power": 500,
                "target_soc": 80,
            },
            blocking=True,
        )

    # Verify correct translation key is used for the error (for multiple coordinators)
    assert exc_info.value.translation_key == "service_call_failed"
