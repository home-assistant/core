"""Tests for Indevolt services/actions."""

from unittest.mock import AsyncMock

from indevolt_api import (
    IndevoltConfig,
    IndevoltEnergyMode,
    PowerExceedsMaxError,
    SocBelowMinimumError,
)
import pytest

from homeassistant.components.indevolt.const import DOMAIN
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
@pytest.mark.parametrize(
    ("service_name", "power", "target_soc"),
    [
        ("charge", 1200, 60),
        ("discharge", 1200, 40),
    ],
)
async def test_service_charge_discharge(
    hass: HomeAssistant,
    mock_indevolt: AsyncMock,
    mock_config_entry: MockConfigEntry,
    service_name: str,
    power: int,
    target_soc: int,
) -> None:
    """Test charge and discharge services."""
    await setup_integration(hass, mock_config_entry)

    # Reset mock call count for this iteration
    mock_indevolt.set_data.reset_mock()

    # Mock call to start service
    await hass.services.async_call(
        DOMAIN,
        service_name,
        {
            "device_id": [_get_device_id(hass, mock_config_entry)],
            "power": power,
            "target_soc": target_soc,
        },
        blocking=True,
    )

    # Verify energy mode switch and charge/discharge were called correctly
    mock_indevolt.set_data.assert_called_once_with(
        IndevoltConfig.WRITE_ENERGY_MODE, IndevoltEnergyMode.REAL_TIME_CONTROL
    )
    if service_name == "charge":
        mock_indevolt.charge.assert_called_once_with(power, target_soc)
    else:
        mock_indevolt.discharge.assert_called_once_with(power, target_soc)


@pytest.mark.parametrize("generation", [1], indirect=True)
@pytest.mark.parametrize(
    ("service_name", "power", "target_soc"),
    [
        ("charge", 1300, 60),
        ("discharge", 1000, 20),
    ],
)
async def test_service_power_too_high(
    hass: HomeAssistant,
    mock_indevolt: AsyncMock,
    mock_config_entry: MockConfigEntry,
    service_name: str,
    power: int,
    target_soc: int,
) -> None:
    """Test charge and discharge service validation for max power."""
    await setup_integration(hass, mock_config_entry)

    # Configure the API mock to raise PowerExceedsMaxError for exceeded power
    mock_indevolt.check_charge_limits.side_effect = PowerExceedsMaxError(power, 1200, 1)
    mock_indevolt.check_discharge_limits.side_effect = PowerExceedsMaxError(
        power, 800, 1
    )

    # Mock call to start service (exceed max power for gen 1)
    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            service_name,
            {
                "device_id": [_get_device_id(hass, mock_config_entry)],
                "power": power,
                "target_soc": target_soc,
            },
            blocking=True,
        )

    # Verify correct translation key is used for the error
    assert exc_info.value.translation_key == "power_exceeds_max"


@pytest.mark.parametrize("generation", [2], indirect=True)
@pytest.mark.parametrize("service_name", ["charge", "discharge"])
async def test_service_target_soc_below_minimum(
    hass: HomeAssistant,
    mock_indevolt: AsyncMock,
    mock_config_entry: MockConfigEntry,
    service_name: str,
) -> None:
    """Test charge and discharge service validation when SOC is below the library hard minimum."""
    await setup_integration(hass, mock_config_entry)

    # Configure the API mock to raise SocBelowMinimumError
    mock_indevolt.check_charge_limits.side_effect = SocBelowMinimumError(3, 5, 2)
    mock_indevolt.check_discharge_limits.side_effect = SocBelowMinimumError(3, 5, 2)

    # Mock call to start service (target SOC below hard minimum)
    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            service_name,
            {
                "device_id": [_get_device_id(hass, mock_config_entry)],
                "power": 500,
                "target_soc": 3,
            },
            blocking=True,
        )

    # Verify correct translation key is used for the error
    assert exc_info.value.translation_key == "soc_below_minimum"


@pytest.mark.parametrize("generation", [2], indirect=True)
@pytest.mark.parametrize("service_name", ["charge", "discharge"])
async def test_service_target_soc_below_emergency(
    hass: HomeAssistant,
    mock_indevolt: AsyncMock,
    mock_config_entry: MockConfigEntry,
    service_name: str,
) -> None:
    """Test charge and discharge service validation for target SOC."""
    await setup_integration(hass, mock_config_entry)

    # Mock call to start service (target SOC below Emergency SOC (soft limit))
    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            service_name,
            {
                "device_id": [_get_device_id(hass, mock_config_entry)],
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
                "device_id": ["non-existent-device-id"],
                "power": 500,
                "target_soc": 50,
            },
            blocking=True,
        )

    # Verify correct translation key is used for the error
    assert exc_info.value.translation_key == "no_matching_target_entries"


@pytest.mark.parametrize("generation", [2], indirect=True)
@pytest.mark.parametrize("alt_generation", [1], indirect=True)
@pytest.mark.parametrize(
    ("service_name", "power", "target_soc"),
    [
        ("charge", 1300, 60),
        ("discharge", 1000, 20),
    ],
)
async def test_multi_device_partial_validation_failure(
    hass: HomeAssistant,
    mock_indevolt: AsyncMock,
    mock_config_entry: MockConfigEntry,
    alt_mock_config_entry: MockConfigEntry,
    service_name: str,
    power: int,
    target_soc: int,
) -> None:
    """Test charge and discharge with two devices where only the gen 1 device fails power validation."""

    # Set up multiple devices (gen 1 & gen 2)
    await setup_integration(hass, mock_config_entry)
    await setup_integration(hass, alt_mock_config_entry)

    # Configure the mock to raise PowerExceedsMaxError only for gen 1 devices
    def raise_if_gen1_charge(p: int, soc: int, generation: int) -> None:
        if generation == 1:
            raise PowerExceedsMaxError(p, 1200, generation)

    def raise_if_gen1_discharge(p: int, soc: int, generation: int) -> None:
        if generation == 1:
            raise PowerExceedsMaxError(p, 800, generation)

    mock_indevolt.check_charge_limits.side_effect = raise_if_gen1_charge
    mock_indevolt.check_discharge_limits.side_effect = raise_if_gen1_discharge

    # Mock call to start service on both devices (exceed max power for gen 1)
    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            service_name,
            {
                "device_id": [
                    _get_device_id(hass, mock_config_entry),
                    _get_device_id(hass, alt_mock_config_entry),
                ],
                "power": power,
                "target_soc": target_soc,
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
@pytest.mark.parametrize("service_name", ["charge", "discharge"])
async def test_multi_device_full_validation_failure(
    hass: HomeAssistant,
    mock_indevolt: AsyncMock,
    mock_config_entry: MockConfigEntry,
    alt_mock_config_entry: MockConfigEntry,
    service_name: str,
) -> None:
    """Test charge and discharge with two devices where both fail SOC validation."""

    # Set up multiple devices (gen 1 & gen 2)
    await setup_integration(hass, mock_config_entry)
    await setup_integration(hass, alt_mock_config_entry)

    # Mock call to start service on both devices (target SOC < emergency SOC for both)
    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            service_name,
            {
                "device_id": [
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
    assert f"{mock_config_entry.title}: " in errors
    assert f"{alt_mock_config_entry.title}: " in errors


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
    coordinator.data[IndevoltConfig.READ_ENERGY_MODE] = (
        IndevoltEnergyMode.OUTDOOR_PORTABLE
    )

    # Mock call to start charging (device in outdoor/portable mode)
    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            "charge",
            {
                "device_id": [_get_device_id(hass, mock_config_entry)],
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
    del coordinator.data[IndevoltConfig.READ_ENERGY_MODE]

    # Mock call to start charging (current energy mode unknown)
    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            "charge",
            {
                "device_id": [_get_device_id(hass, mock_config_entry)],
                "power": 500,
                "target_soc": 80,
            },
            blocking=True,
        )

    # Verify correct translation key is used for the error
    assert exc_info.value.translation_key == "failed_to_retrieve_current_energy_mode"


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
                "device_id": [_get_device_id(hass, mock_config_entry)],
                "power": 500,
                "target_soc": 80,
            },
            blocking=True,
        )

    # Verify correct translation key is used for the error (for single coordinator)
    assert str(exc_info.value) == "Device push failed"
    assert exc_info.value.translation_key is None


@pytest.mark.parametrize("generation", [2], indirect=True)
@pytest.mark.parametrize("alt_generation", [1], indirect=True)
async def test_multi_device_execution_failure(
    hass: HomeAssistant,
    mock_indevolt: AsyncMock,
    mock_config_entry: MockConfigEntry,
    alt_mock_config_entry: MockConfigEntry,
) -> None:
    """Test that multi_device_errors is raised when execution fails for multiple devices."""

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
                "device_id": [
                    _get_device_id(hass, mock_config_entry),
                    _get_device_id(hass, alt_mock_config_entry),
                ],
                "power": 500,
                "target_soc": 80,
            },
            blocking=True,
        )

    # Verify correct translation key is used for the error (for multiple coordinators)
    assert exc_info.value.translation_key == "multi_device_errors"
