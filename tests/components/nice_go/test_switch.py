"""Nice G.O. switch tests."""

from unittest.mock import AsyncMock

from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


async def test_turn_on(
    hass: HomeAssistant, mock_nice_go: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test turn on switch."""
    await setup_integration(hass, mock_config_entry, [Platform.SWITCH])
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.test_garage_1_vacation_mode"},
        blocking=True,
    )
    mock_nice_go.vacation_mode_on.assert_called_once_with("1")


async def test_turn_off(
    hass: HomeAssistant, mock_nice_go: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test turn off switch."""
    await setup_integration(hass, mock_config_entry, [Platform.SWITCH])
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.test_garage_2_vacation_mode"},
        blocking=True,
    )
    mock_nice_go.vacation_mode_off.assert_called_once_with("2")
