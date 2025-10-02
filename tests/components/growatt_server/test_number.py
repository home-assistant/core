"""Tests for the Growatt Server number platform."""

from unittest.mock import MagicMock

from growattServer import GrowattV1ApiError
import pytest

from homeassistant.components.growatt_server.number import GrowattNumber
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError


async def test_number_native_value(
    hass: HomeAssistant,
    mock_number_entity: GrowattNumber,
) -> None:
    """Test getting the native value."""
    # Mock coordinator data
    mock_number_entity.coordinator.data = {"chargePowerCommand": 75}

    assert mock_number_entity.native_value == 75


async def test_number_native_value_none(
    hass: HomeAssistant,
    mock_number_entity: GrowattNumber,
) -> None:
    """Test getting the native value when data is None."""
    # Mock coordinator data without the key
    mock_number_entity.coordinator.data = {}

    assert mock_number_entity.native_value is None


async def test_number_set_value_success(
    hass: HomeAssistant,
    mock_number_entity: GrowattNumber,
) -> None:
    """Test setting a number value successfully."""
    mock_number_entity.coordinator.data = {"chargePowerCommand": 40}

    # Mock the API call
    mock_number_entity.coordinator.api.min_write_parameter = MagicMock(return_value="")

    await mock_number_entity.async_set_native_value(80)

    # Verify API was called correctly
    mock_number_entity.coordinator.api.min_write_parameter.assert_called_once_with(
        "ABC123MIN456", "charge_power", 80
    )

    # Verify coordinator data was updated
    assert mock_number_entity.coordinator.data["chargePowerCommand"] == 80


async def test_number_set_value_api_error(
    hass: HomeAssistant,
    mock_number_entity: GrowattNumber,
) -> None:
    """Test setting a number value when API returns an error."""
    mock_number_entity.coordinator.data = {"chargePowerCommand": 40}

    # Mock the API call to raise an error
    mock_number_entity.coordinator.api.min_write_parameter = MagicMock(
        side_effect=GrowattV1ApiError("API rate limit exceeded")
    )

    with pytest.raises(HomeAssistantError, match="Error while setting parameter"):
        await mock_number_entity.async_set_native_value(80)

    # Verify coordinator data was NOT updated
    assert mock_number_entity.coordinator.data["chargePowerCommand"] == 40
