"""Tests for the Envisalink keypad sensor."""

from unittest.mock import MagicMock

from homeassistant.core import HomeAssistant

from .conftest import KEYPAD_ENTITY, setup_envisalink


async def test_keypad_native_value(
    hass: HomeAssistant, mock_controller: MagicMock
) -> None:
    """Test the keypad sensor shows the partition alpha text."""
    assert await setup_envisalink(hass)
    assert hass.states.get(KEYPAD_ENTITY).state == "Ready"

    mock_controller.alarm_state["partition"][1]["status"]["alpha"] = "Armed Away"
    # A matching partition delivered as a string is coerced and applies.
    mock_controller.callback_keypad_update("1")
    await hass.async_block_till_done()

    assert hass.states.get(KEYPAD_ENTITY).state == "Armed Away"


async def test_keypad_attributes_expose_status(
    hass: HomeAssistant, mock_controller: MagicMock
) -> None:
    """Test the keypad sensor exposes the full partition status as attributes."""
    assert await setup_envisalink(hass)

    attrs = hass.states.get(KEYPAD_ENTITY).attributes
    assert attrs["armed_away"] is False
    assert attrs["alpha"] == "Ready"
