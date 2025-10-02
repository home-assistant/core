"""Tests for the Growatt Server switch platform."""

from unittest.mock import MagicMock

from growattServer import GrowattV1ApiError
import pytest

from homeassistant.components.growatt_server.switch import GrowattSwitch
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError


async def test_switch_is_on_string_value(
    hass: HomeAssistant,
    mock_switch_entity: GrowattSwitch,
) -> None:
    """Test is_on property with string value."""
    # Mock coordinator data with string "1"
    mock_switch_entity.coordinator.data = {"acChargeEnable": "1"}

    assert mock_switch_entity.is_on is True


async def test_switch_is_on_integer_value(
    hass: HomeAssistant,
    mock_switch_entity: GrowattSwitch,
) -> None:
    """Test is_on property with integer value."""
    # Mock coordinator data with integer 1
    mock_switch_entity.coordinator.data = {"acChargeEnable": 1}

    assert mock_switch_entity.is_on is True


async def test_switch_is_off(
    hass: HomeAssistant,
    mock_switch_entity: GrowattSwitch,
) -> None:
    """Test is_on property when switch is off."""
    # Mock coordinator data with 0
    mock_switch_entity.coordinator.data = {"acChargeEnable": 0}

    assert mock_switch_entity.is_on is False


async def test_switch_pending_state(
    hass: HomeAssistant,
    mock_switch_entity: GrowattSwitch,
) -> None:
    """Test that pending state is shown during operation."""
    mock_switch_entity.coordinator.data = {"acChargeEnable": 0}
    mock_switch_entity._pending_state = True

    # Pending state should override coordinator data
    assert mock_switch_entity.is_on is True


async def test_switch_turn_on_success(
    hass: HomeAssistant,
    mock_switch_entity: GrowattSwitch,
) -> None:
    """Test turning on the switch successfully."""
    mock_switch_entity.coordinator.data = {"acChargeEnable": 0}

    # Mock the API call
    mock_switch_entity.coordinator.api.min_write_parameter = MagicMock(return_value="")

    await mock_switch_entity.async_turn_on()

    # Verify API was called correctly
    mock_switch_entity.coordinator.api.min_write_parameter.assert_called_once_with(
        "ABC123MIN456", "ac_charge", "1"
    )

    # Verify coordinator data was updated
    assert mock_switch_entity.coordinator.data["acChargeEnable"] == "1"

    # Verify pending state was cleared
    assert mock_switch_entity._pending_state is None


async def test_switch_turn_off_success(
    hass: HomeAssistant,
    mock_switch_entity: GrowattSwitch,
) -> None:
    """Test turning off the switch successfully."""
    mock_switch_entity.coordinator.data = {"acChargeEnable": 1}

    # Mock the API call
    mock_switch_entity.coordinator.api.min_write_parameter = MagicMock(return_value="")

    await mock_switch_entity.async_turn_off()

    # Verify API was called correctly
    mock_switch_entity.coordinator.api.min_write_parameter.assert_called_once_with(
        "ABC123MIN456", "ac_charge", "0"
    )

    # Verify coordinator data was updated
    assert mock_switch_entity.coordinator.data["acChargeEnable"] == "0"


async def test_switch_turn_on_api_error(
    hass: HomeAssistant,
    mock_switch_entity: GrowattSwitch,
) -> None:
    """Test turning on the switch when API returns an error."""
    mock_switch_entity.coordinator.data = {"acChargeEnable": 0}

    # Mock the API call to raise an error
    mock_switch_entity.coordinator.api.min_write_parameter = MagicMock(
        side_effect=GrowattV1ApiError("Too many requests")
    )

    with pytest.raises(HomeAssistantError, match="Error while setting switch state"):
        await mock_switch_entity.async_turn_on()

    # Verify coordinator data was NOT updated
    assert mock_switch_entity.coordinator.data["acChargeEnable"] == 0

    # Verify pending state was cleared
    assert mock_switch_entity._pending_state is None
