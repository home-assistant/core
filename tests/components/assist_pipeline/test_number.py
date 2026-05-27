"""Tests for Assist pipeline number entities."""

from unittest.mock import AsyncMock, patch

from homeassistant.components.assist_pipeline.number import CommandTimeoutNumber
from homeassistant.components.assist_pipeline.vad import (
    DEFAULT_COMMAND_TIMEOUT_SECONDS,
    MAX_COMMAND_TIMEOUT_SECONDS,
    MIN_COMMAND_TIMEOUT_SECONDS,
)
from homeassistant.components.number import (
    NumberDeviceClass,
    NumberExtraStoredData,
    NumberMode,
)
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant


async def test_command_timeout_number_restore(hass: HomeAssistant) -> None:
    """Test restoring command timeout number value."""
    number = CommandTimeoutNumber("test")
    number.hass = hass
    restored = NumberExtraStoredData(
        native_max_value=MAX_COMMAND_TIMEOUT_SECONDS,
        native_min_value=MIN_COMMAND_TIMEOUT_SECONDS,
        native_step=1.0,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        native_value=30.0,
    )

    with (
        patch.object(
            number, "async_get_last_number_data", AsyncMock(return_value=restored)
        ),
        patch.object(number, "async_write_ha_state"),
    ):
        await number.async_added_to_hass()

    assert number.native_value == 30.0


async def test_command_timeout_number_clamps_value() -> None:
    """Test command timeout number clamps values to the supported range."""
    number = CommandTimeoutNumber("test")

    with patch.object(number, "async_write_ha_state"):
        await number.async_set_native_value(MAX_COMMAND_TIMEOUT_SECONDS + 1)

    assert number.native_value == MAX_COMMAND_TIMEOUT_SECONDS

    with patch.object(number, "async_write_ha_state"):
        await number.async_set_native_value(MIN_COMMAND_TIMEOUT_SECONDS - 1)

    assert number.native_value == MIN_COMMAND_TIMEOUT_SECONDS


def test_command_timeout_number_attributes() -> None:
    """Test command timeout number attributes."""
    number = CommandTimeoutNumber("test")

    assert number.unique_id == "test-command_timeout"
    assert number.native_value == DEFAULT_COMMAND_TIMEOUT_SECONDS
    assert number.native_min_value == MIN_COMMAND_TIMEOUT_SECONDS
    assert number.native_max_value == MAX_COMMAND_TIMEOUT_SECONDS
    assert number.native_step == 1.0
    assert number.native_unit_of_measurement == UnitOfTime.SECONDS
    assert number.device_class == NumberDeviceClass.DURATION
    assert number.mode == NumberMode.BOX
