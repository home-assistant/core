"""Tests for the Electra Smart climate entity."""

from unittest.mock import Mock

from electrasmart.device import OperationMode

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_HVAC_MODE,
    HVACMode,
)
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.core import HomeAssistant

ENTITY_ID = "climate.living_room"


async def test_turn_on_keeps_the_mode_the_ac_was_last_running_in(
    hass: HomeAssistant, mock_api: Mock, mock_device: Mock, setup_integration: None
) -> None:
    """Turning on must not force a mode on the device."""
    await hass.services.async_call(
        CLIMATE_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )

    mock_device.turn_on.assert_called_once_with()
    mock_device.set_mode.assert_not_called()
    mock_api.set_state.assert_awaited_once_with(mock_device)


async def test_turn_on_falls_back_to_cool_when_no_mode_can_be_restored(
    hass: HomeAssistant, mock_api: Mock, mock_device: Mock, setup_integration: None
) -> None:
    """A unit that reports no previous mode must still turn on."""
    mock_device.turn_on = Mock(return_value=False)

    await hass.services.async_call(
        CLIMATE_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )

    mock_device.turn_on.assert_called_once_with()
    mock_device.set_mode.assert_called_once_with(OperationMode.MODE_COOL)
    mock_api.set_state.assert_awaited_once_with(mock_device)


async def test_turn_off_turns_the_device_off(
    hass: HomeAssistant, mock_api: Mock, mock_device: Mock, setup_integration: None
) -> None:
    """Turning off goes through set_hvac_mode, which calls turn_off()."""
    await hass.services.async_call(
        CLIMATE_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )

    mock_device.turn_off.assert_called_once_with()
    mock_api.set_state.assert_awaited_once_with(mock_device)


async def test_set_hvac_mode_still_selects_the_requested_mode(
    hass: HomeAssistant, mock_api: Mock, mock_device: Mock, setup_integration: None
) -> None:
    """Explicitly picking a mode must keep working."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_HVAC_MODE: HVACMode.COOL},
        blocking=True,
    )

    mock_device.set_mode.assert_called_once_with(OperationMode.MODE_COOL)
    mock_device.turn_on.assert_called_once_with()
    mock_api.set_state.assert_awaited_once_with(mock_device)
