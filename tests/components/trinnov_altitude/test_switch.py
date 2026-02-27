"""Tests for Trinnov Altitude switch platform."""

from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from . import MOCK_ID

from tests.common import MockConfigEntry

MUTE_ENTITY_ID = f"switch.trinnov_altitude_{MOCK_ID}_mute"
DIM_ENTITY_ID = f"switch.trinnov_altitude_{MOCK_ID}_dim"
BYPASS_ENTITY_ID = f"switch.trinnov_altitude_{MOCK_ID}_bypass"


async def test_entities(
    hass: HomeAssistant,
    mock_device,
    mock_integration: MockConfigEntry,
) -> None:
    """Test switch entities are created."""
    assert hass.states.get(MUTE_ENTITY_ID) is not None
    assert hass.states.get(DIM_ENTITY_ID) is not None
    assert hass.states.get(BYPASS_ENTITY_ID) is not None


async def test_mute_commands(
    hass: HomeAssistant,
    mock_device,
    mock_integration: MockConfigEntry,
) -> None:
    """Test mute switch service calls."""
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: MUTE_ENTITY_ID},
        blocking=True,
    )
    mock_device.mute_set.assert_called_once_with(True)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: MUTE_ENTITY_ID},
        blocking=True,
    )
    mock_device.mute_set.assert_called_with(False)


async def test_dim_and_bypass_commands(
    hass: HomeAssistant,
    mock_device,
    mock_integration: MockConfigEntry,
) -> None:
    """Test dim and bypass switch service calls."""
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: DIM_ENTITY_ID},
        blocking=True,
    )
    mock_device.dim_set.assert_called_once_with(True)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: BYPASS_ENTITY_ID},
        blocking=True,
    )
    mock_device.bypass_set.assert_called_once_with(True)
